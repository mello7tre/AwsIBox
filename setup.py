import setuptools

setuptools.setup(
    packages=[
        'awsibox',
    ],
    package_data={
        'awsibox': ['cfg/BASE/*'],
        'awsibox': ['templates/*'],
        'awsibox': ['lambdas/*'],
    },
    install_requires=[
        'troposphere',
        'PyYAML>=5,==5.*',
    ],
    python_requires='>=3.7',
    scripts=[
        'scripts/ibox_generate_templates.py',
    ],
    include_package_data=True,
)
