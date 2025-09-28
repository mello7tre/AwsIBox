#!/bin/sh
COMMIT=$(git rev-parse --short HEAD)
sed -i "s#\(__version__ =[^\"]\+\"[^\" ]\+\).*#\1+$COMMIT\"#" awsibox/__init__.py
pip3 install .
rm -fr awsibox.egg-info build
git checkout awsibox/__init__.py
