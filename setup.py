import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="awsibox",
    version="0.1.0",
    author="Mello",
    author_email="mello+python@ankot.org",
    description="AWS Infrastructure in a Box",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mello7tre/AwsIBox",
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
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    include_package_data=True,
)
