"""
Android Bluetooth Low Energy
"""
from pythonforandroid.recipe import PythonRecipe
from pythonforandroid.toolchain import current_directory, info, shprint
import sh
from os import environ
from os.path import isdir, join


class LXSTRecipe(PythonRecipe):
    name = 'lxst_recipe'
    depends = ['python3', 'setuptools', 'android', "cffi"]
    call_hostpython_via_targetpython = False
    install_in_hostpython = True

    def prepare_build_dir(self, arch):
        build_dir = self.get_build_dir(arch)
        assert build_dir.endswith(self.name)
        shprint(sh.rm, '-rf', build_dir)
        shprint(sh.mkdir, build_dir)

        source_dir = environ.get(
            'SIDEBAND_LXST_SOURCE_DIR',
            join(self.get_recipe_dir(), '..', '..', '..', 'LXST')
        )
        if not isdir(source_dir):
            raise RuntimeError(
                'LXST source directory was not found: {}'.format(source_dir)
            )

        srcs = ('LXST', 'setup.py', 'README.md')

        for filename in srcs:
            source = join(source_dir, filename)
            print(f"Copy {source} to {build_dir}")
            shprint(sh.cp, '-a', source,
                    build_dir)

    def postbuild_arch(self, arch):
        super(LXSTRecipe, self).postbuild_arch(arch)
        info("LXST native build completed")

recipe = LXSTRecipe()
