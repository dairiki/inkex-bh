from typing import Tuple
from typing import TYPE_CHECKING
from typing import Union

import inkex

if TYPE_CHECKING:
    from lxml.etree import _ElementTree

    SvgElementTree = _ElementTree[inkex.SvgDocumentElement]
else:
    SvgElementTree = object


TransformLike = Union[
    inkex.Transform,
    Tuple[Tuple[float, float, float], Tuple[float, float, float]],
    str,
    None,
]
