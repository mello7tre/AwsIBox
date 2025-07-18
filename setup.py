import setuptools

setuptools.setup(
    packages=[
        "awsibox",
    ],
    package_data={
        "awsibox": ["cfg/*"],
        "awsibox": ["aws/*"],
        "awsibox": ["mod/*"],
        "awsibox": ["templates/*"],
        "awsibox": ["lambdas/*"],
        "awsibox": ["user-data/*"],
    },
    install_requires=[
        "troposphere",
        "PyYAML>=5,==5.*",
        "python_minifier",
        "tqdm",
    ],
    python_requires=">=3.7",
    scripts=[
        "scripts/ibox_generate_templates.py",
    ],
    include_package_data=True,
)
