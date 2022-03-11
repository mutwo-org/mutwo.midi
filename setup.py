import setuptools  # type: ignore


with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

extras_require = {"testing": ["nose", "coveralls"]}

setuptools.setup(
    name="mutwo.ext-midi",
    version="0.5.0",
    license="GPL",
    description="example extension for event based framework for generative art",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Levin Eric Zimmermann",
    author_email="levin.eric.zimmermann@posteo.eu",
    url="https://github.com/mutwo-org/mutwo.ext-midi",
    project_urls={"Documentation": "https://mutwo.readthedocs.io/en/latest/"},
    packages=[
        package
        for package in setuptools.find_namespace_packages(include=["mutwo.*"])
        if package[:5] != "tests"
    ],
    setup_requires=[],
    install_requires=[
        "mutwo.ext-core>=0.54.0, <0.55.0",
        "mutwo.ext-music>=0.8.0, <0.9.0",
        "expenvelope>=0.6.5, <1.0.0",
        "mido>=1.2.9, <2",
        "numpy>=1.18, <2.00",
    ],
    extras_require=extras_require,
    python_requires=">=3.9, <4",
)
