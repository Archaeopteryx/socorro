#!/bin/sh
# This script makes sure that Jenkins can properly run your tests against your
# codebase.
set -e

DB_HOST="localhost"
DB_USER="hudson"

cd $WORKSPACE
VENV=$WORKSPACE/venv

echo "Starting build on executor $EXECUTOR_NUMBER..."

# Make sure there's no old pyc files around.
find . -name '*.pyc' -exec rm {} \;

if [ ! -d "$VENV/bin" ]; then
  echo "No virtualenv found.  Making one..."
  virtualenv $VENV --no-site-packages
  source $VENV/bin/activate
  pip install --upgrade pip
  pip install coverage
fi

git submodule sync -q
git submodule update --init --recursive

if [ ! -d "$WORKSPACE/vendor" ]; then
    echo "No /vendor... crap."
    exit 1
fi

source $VENV/bin/activate
pip install -q -r requirements/dev.txt

pip install -I --install-option="--home=`pwd`/vendor-local" \
    -r requirements/compiled.txt
pip install -I --install-option="--home=`pwd`/vendor-local" \
    -r requirements/prod.txt

cp crashstats/settings/local.py-dist crashstats/settings/local.py

echo "Starting tests..."
./manage.py collectstatic --noinput
./manage.py compress_jingo --force
coverage run manage.py test --noinput --with-xunit
coverage xml $(find crashstats lib -name '*.py')
echo "Tests finished."

echo "Tar it..."
tar --mode 755 --owner 0 --group 0 -zcf ../socorro-crashstats.tar.gz ./*
mv ../socorro-crashstats.tar.gz ./

echo "FIN"
