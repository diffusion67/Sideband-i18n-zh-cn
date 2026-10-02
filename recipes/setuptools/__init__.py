from pythonforandroid.recipe import PyProjectRecipe


class SetuptoolsRecipe(PyProjectRecipe):
    # The pinned p4a recipe has no source URL, so it skips target installation.
    # CFFI uses target site-packages while running setup.py with hostpython.
    # Build the same setuptools version used by the host build environment.
    version = '84.0.0'
    url = 'https://files.pythonhosted.org/packages/source/s/setuptools/setuptools-{version}.tar.gz'
    hostpython_prerequisites = ['setuptools']


recipe = SetuptoolsRecipe()
