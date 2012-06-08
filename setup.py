from setuptools import setup, find_packages

setup(
        name="crow2",
        version="0.1.dev0",
        packages=find_packages(),
        scripts=["bin/crow2"],
        install_requires=["twisted", "zope.interface"]
)
