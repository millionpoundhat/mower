import subprocess
from subprocess import check_output
import sys
import tempfile
import os
import time
import shutil

"""
Due to ctypes, you have to set LD_LIBRARY_PATH ahead of time

    export LD_LIBRARY_PATH=`grass --config path`/lib
    python your_script.py

or

    su
    echo "`grass --config path`/lib" > /etc/ld.so.conf.d/grass.conf
    ldconfig
    exit
    python your_script.py
"""


class GrassSession():
    def __init__(self, src=None, grassbin='/usr/local/bin/grass',
                 persist=True, dir=None):

        # If dir is specified, load existing location or mapset and
        # assume persist=True
        self.persist = persist

        # Else if src is not none, create new location

        # if src
        if type(src) == int:
            # Assume epsg code
            self.location_seed = f"EPSG:{src}"
        else:
            # Assume georeferenced vector or raster
            self.location_seed = src

        self.grassbin = grassbin
        # TODO assert grassbin is executable and supports what we need

        startcmd = f"{grassbin} --config path"

        # Adapted from
        # http://grasswiki.osgeo.org/wiki/Working_with_GRASS_without_starting_it_explicitly#Python:_GRASS_GIS_7_without_existing_location_using_metadata_only
        p = subprocess.Popen(startcmd, shell=True,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out = check_output(startcmd, shell=True).decode("utf-8")
        if p.wait() != 0:
            raise Exception(
                f"ERROR: Cannot find GRASS GIS 8 start script ({startcmd})")
        if sys.platform.startswith('linux'):
            self.gisbase = out.strip('\n')
        elif sys.platform.startswith('win'):
            if out.find("OSGEO4W home is") != -1:
                self.gisbase = out.strip().split('\n')[1]
            else:
                self.gisbase = out.strip('\n')

        self.gisdb = os.path.join(tempfile.gettempdir(), 'mowerdb')
        self.location = f"loc_{str(time.time()).replace('.', '_')}"
        self.mapset = "PERMANENT"

        os.environ['GISBASE'] = self.gisbase
        os.environ['GISDBASE'] = self.gisdb

        # path = os.getenv('LD_LIBRARY_PATH')
        # ldir = os.path.join(self.gisbase, 'lib')
        # if path:
        #     path = ldir + os.pathsep + path
        # else:
        #     path = ldir
        # os.environ['LD_LIBRARY_PATH'] = path

    def gsetup(self):
        path = os.path.join(self.gisbase, 'etc', 'python')
        sys.path.append(path)
        os.environ['PYTHONPATH'] = ':'.join(sys.path)

        import grass.script.setup as gsetup
        gsetup.init(self.gisdb, self.location, self.mapset, self.gisbase)

    def create_location(self):
        try:
            os.stat(self.gisdb)
        except OSError:
            os.mkdir(self.gisdb)

        createcmd = "{0} -c {1} -e {2}".format(
            self.grassbin,
            self.location_seed,
            self.location_path)

        print("Creating the GRASS location with the following command" + createcmd)
        p = subprocess.Popen(createcmd, shell=True,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()
        if p.wait() != 0:
            raise Exception(
                f"ERROR: GRASS GIS 8 start script ({createcmd})")

    @property
    def location_path(self):
        return os.path.join(self.gisdb, self.location)

    def cleanup(self):
        if os.path.exists(self.location_path) and not self.persist:
            shutil.rmtree(self.location_path)
        if 'GISRC' in os.environ:
            del os.environ['GISRC']

    def __enter__(self):
        self.create_location()
        self.gsetup()
        # except:
        #     self.cleanup()
        return self

    def __exit__(self, type, value, traceback):
        self.cleanup()
