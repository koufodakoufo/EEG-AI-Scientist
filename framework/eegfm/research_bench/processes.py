"""Linux owned-descendant accounting, including children that create new PGIDs."""
from __future__ import annotations
import ctypes
import os
from pathlib import Path
import signal
import time
from typing import Any


def process_info(pid: int) -> dict[str, int | str] | None:
    try:
        path=Path('/proc')/str(pid)
        if path.stat().st_uid != os.getuid(): return None
        fields=(path/'stat').read_text().rsplit(')',1)[1].split()
        return {'pid':pid,'ppid':int(fields[1]),'pgid':int(fields[2]),'start':int(fields[19]),
                'rss':int(fields[21])*os.sysconf('SC_PAGE_SIZE'),'state':fields[0]}
    except (OSError,ValueError,IndexError): return None


def snapshot() -> dict[int, dict[str, int | str]]:
    result={}
    for path in Path('/proc').iterdir():
        if path.name.isdigit():
            info=process_info(int(path.name))
            if info is not None: result[int(path.name)]=info
    return result


class OwnedProcessTree:
    """Make this dedicated launcher a subreaper so orphaned descendants stay owned.

    PID start ticks are checked before every signal. The caller must not launch
    unrelated children concurrently from the same Python process while active.
    Existing children are excluded. No other user's processes are inspected.
    """
    def __init__(self) -> None:
        self.parent=os.getpid()
        self.before=set(snapshot())
        self.known: dict[int,int]={}
        self.root_start=0
        self.root_pid=0
        self.libc=ctypes.CDLL(None,use_errno=True)
        previous=ctypes.c_int()
        if self.libc.prctl(37,ctypes.byref(previous),0,0,0) != 0:
            raise OSError(ctypes.get_errno(),'PR_GET_CHILD_SUBREAPER failed')
        self.previous=previous.value
        if self.libc.prctl(36,1,0,0,0) != 0:
            raise OSError(ctypes.get_errno(),'PR_SET_CHILD_SUBREAPER failed')

    def attach(self,pid: int) -> None:
        info=process_info(pid)
        if info is None: raise RuntimeError('Cannot establish owned process identity')
        self.root_start=int(info['start']); self.root_pid=pid; self.known[pid]=self.root_start

    def refresh(self) -> dict[int,dict[str,int|str]]:
        current=snapshot()
        active={pid:info for pid,info in current.items() if self.known.get(pid)==info['start']}
        changed=True
        while changed:
            changed=False
            for pid,info in current.items():
                if pid in self.before or pid in active or int(info['start']) < self.root_start: continue
                if info['ppid'] in active or info['ppid']==self.parent:
                    self.known[pid]=int(info['start']); active[pid]=info; changed=True
        return active

    def rss_bytes(self) -> int:
        return sum(int(info['rss']) for info in self.refresh().values())

    def _signal(self,signum: int) -> None:
        for pid,start in list(self.known.items()):
            info=process_info(pid)
            if info is not None and info['start']==start:
                try: os.kill(pid,signum)
                except ProcessLookupError: pass

    def terminate(self) -> dict[str,Any]:
        self.refresh(); self._signal(signal.SIGTERM)
        time.sleep(0.15)
        self.refresh(); self._signal(signal.SIGKILL)
        # Allow reparenting and collect children which changed process group or
        # whose parent exited between monitor samples.
        for _ in range(10):
            live=self.refresh()
            for pid,info in live.items():
                if info['ppid']==self.parent and pid!=self.root_pid:
                    try: os.waitpid(pid,os.WNOHANG)
                    except ChildProcessError: pass
            active={pid:info for pid,info in self.refresh().items() if info['state']!='Z'}
            if not active: break
            self._signal(signal.SIGKILL); time.sleep(0.05)
        survivors=[pid for pid,info in self.refresh().items() if info['state']!='Z']
        self.libc.prctl(36,self.previous,0,0,0)
        return {'tracked_process_count':len(self.known),'surviving_owned_pids':survivors,
                'subreaper':True,'identity_check':'pid+start_ticks+same_uid','accounting':'descendant_tree_rss_sum'}
