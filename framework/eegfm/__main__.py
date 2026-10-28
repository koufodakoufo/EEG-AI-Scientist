import sys

if len(sys.argv) > 1 and sys.argv[1] == "research-bench":
    from .research_bench.__main__ import main
    sys.exit(main(sys.argv[2:]))
else:
    from .cli import main
    sys.exit(main())
