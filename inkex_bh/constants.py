# Copyright (C) 2019–2022 Geoffrey T. Dairiki <dairiki@dairiki.org>
import inkex
from lxml.etree import register_namespace  # type: ignore[attr-defined]

NSMAP = {
    **inkex.NSS,
    "bh": "http://dairiki.org/barnhunt/inkscape-extensions",
}

register_namespace("bh", NSMAP["bh"])


#################################################################
#
# Custom attributes used by bh-hide-rats

# bh:rat-placement="boundary" marks elements which serve as containing
# boundaries for rat placement
#
# bh:rat-placement="exclude" marks elements which exlude rat placement
# from their boundaries
BH_RAT_PLACEMENT = f"{{{NSMAP['bh']}}}rat-placement"

# bh:rat-guide-mode="layer" marks the rat placement "resist layer"
#
# bh:rat-guide-mode="exclusions" marks exclusion areas on the reset layer
#
# bh:rat-guide-mode="notation" used for notational marks.  These do not
# influence rat placement, but serve a visual notes to the user.
#
# bh:rat-guide-mode="boundary" used to be used for boundary marks on the
# resist layer.  These are no longer used.
BH_RAT_GUIDE_MODE = f"{{{NSMAP['bh']}}}rat-guide-mode"

#################################################################
#
# Custom attributes used by bh-count-symbols

# bh:count-as="bale-48x24x18"  This attribute, when placed
# on a <svg:symbol> element causes it to be counted by an
# alternate name.  (By default they are counted by the symbol's
# id.)
BH_COUNT_AS = f"{{{NSMAP['bh']}}}count-as"

#################################################################
#
# Custom attributes used by bh-create-inset

# bh:inset--export-id="rect123" This attribute is placed on a
# created <svg:image> tag to indicate the id of the element
# which defines the bounding box of the image.
BH_INSET_EXPORT_ID = f"{{{NSMAP['bh']}}}inset--export-id"

# bh:inset--visible-layers="layer3 layer11" This attribute is placed on a
# created <svg:image> tag to indicate the ids of the layers which
# were visible when the image was created.
BH_INSET_VISIBLE_LAYERS = f"{{{NSMAP['bh']}}}inset--visible-layers"


#################################################################
#
# Custom attributes used by random-seed extension

# bh:random-seed="42" This attribute is placed on the
# created <svg:svg> tag to specify a random seed which is used
# by the barnhunt program when expanding template strings
# during export of PDFs.  Setting a fixed random-seed in this
# may ensures that things like the Master rat counts are stable
# when the drawing is edited.

BH_RANDOM_SEED = f"{{{NSMAP['bh']}}}random-seed"
