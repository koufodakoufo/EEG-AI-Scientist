"""Editable posttraining representation only; downstream always uses fixed flatten."""
from torch import nn
from isa_loss import flatten_normalize


def build_representation(token_shape):
    # R1 faithfully uses all official [channel,patch,embedding] tokens.
    # A reviewed R2 may implement aggregation/projector here; encoder exports
    # contain only REVE weights and the immutable downstream remains flatten.
    return nn.Identity()


def represent(tokens, representation):
    return flatten_normalize(representation(tokens))
