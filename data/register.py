from python_toolbox.project import Registry

from .asset.type.base import Base_Asset
from .node.type.base import Base_Node


ASSET_REGISTRY = Registry[type[Base_Asset]]("Asset", Base_Asset)
NODE_REGISTRY = Registry[type[Base_Node]]("Node", Base_Node)