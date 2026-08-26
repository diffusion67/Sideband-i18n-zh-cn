from pythonforandroid.recipe import Recipe
from pythonforandroid.toolchain import current_directory, shprint
import sh


class OpusFileRecipe(Recipe):
    version = "0.12"
    url = "https://downloads.xiph.org/releases/opus/opusfile-{version}.tar.gz"
    depends = ['libogg', 'libopus']
    built_libraries = {'libopusfile.so': '.libs'}

    def build_arch(self, arch):
        with current_directory(self.get_build_dir(arch.arch)):
            env = self.get_recipe_env(arch)
            flags = [
                "--host=" + arch.command_prefix,
                "--disable-http",
                "--disable-examples",
                "--disable-doc",
                "--disable-largefile",
            ]

            libogg_recipe = Recipe.get_recipe('libogg', self.ctx)
            libopus_recipe = Recipe.get_recipe('libopus', self.ctx)
            libogg_dir = libogg_recipe.get_build_dir(arch.arch)
            libopus_dir = libopus_recipe.get_build_dir(arch.arch)

            env['DEPS_CFLAGS'] = '-I{}/include -I{}/include'.format(
                libogg_dir, libopus_dir
            )
            env['DEPS_LIBS'] = '-L{}/.libs -logg -L{}/.libs -lopus'.format(
                libogg_dir, libopus_dir
            )
            
            configure = sh.Command('./configure')
            shprint(configure, *flags, _env=env)
            shprint(sh.make, _env=env)


recipe = OpusFileRecipe()
