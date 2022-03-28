import os
from setuptools import setup, find_packages

setup(
    name="bottle",
    version="0.1",
    description="Solves wordles",
    author="Craig de Stigter",
    author_email="craig@destigter.nz",
    license="MIT",
    packages=["bottle"],
    include_package_data=True,
    install_requires=["click", "requests", "ipdb"],
    zip_safe=False,
    entry_points={
        "console_scripts": [
            "bottle = bottle.cli:main",
        ],
    },
)
