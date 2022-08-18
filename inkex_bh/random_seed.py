# Copyright (C) 2019–2022 Geoffrey T. Dairiki <dairiki@dairiki.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
""" Set/update random seed in /svg/@bh:random-seed
"""
import random
from argparse import ArgumentParser

import inkex
from inkex.localization import inkex_gettext as _

from .constants import BH_RANDOM_SEED


class RandomSeed(inkex.Effect):  # type: ignore[misc]
    def add_arguments(self, pars: ArgumentParser) -> None:
        pars.add_argument("--tab")
        pars.add_argument("--force-reseed", type=inkex.Boolean, default=False)

    def effect(self) -> bool:
        svg = self.svg
        opts = self.options

        has_random_seed = BH_RANDOM_SEED in svg.attrib
        if not opts.force_reseed and has_random_seed:
            inkex.errormsg(_("Random seed is already set."))
            return False

        svg.set(BH_RANDOM_SEED, str(random.randrange(2**128)))
        return True


if __name__ == "__main__":
    RandomSeed().run()
