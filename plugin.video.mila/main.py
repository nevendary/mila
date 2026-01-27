# -*- coding: utf-8 -*-
# Module: default
# Author: nevendary
# Created on: 27.1.2024
# License: AGPL v.3 https://www.gnu.org/licenses/agpl-3.0.html

import sys
import mila

if __name__ == '__main__':
    mila.router(sys.argv[2][1:] if len(sys.argv) > 2 else '')
