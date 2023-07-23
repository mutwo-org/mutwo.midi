import setuptools  # type: ignore

version = {}
with open("mutwo/midi_version/__init__.py") as fp:
    exec(fp.read(), version)

VERSION = version["VERSION"]

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

extras_require = {"testing": ["pytest>=7.1.1"]}

setuptools.setup(
    name="mutwo.midi",
    version=VERSION,
    license="GPL",
    description="midi extension for event based framework mutwo",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Levin Eric Zimmermann",
    author_email="levin.eric.zimmermann@posteo.eu",
    url="https://github.com/mutwo-org/mutwo.midi",
    project_urls={"Documentation": "https://mutwo.readthedocs.io/en/latest/"},
    packages=[
        package
        for package in setuptools.find_namespace_packages(include=["mutwo.*"])
        if package[:5] != "tests"
    ],
    setup_requires=[],
    install_requires=[
        "mutwo.core>=1.3.0, <2.0.0",
        "mutwo.music>=0.19.0, <1.0.0",
        "mido>=1.2.9, <2",
        "numpy>=1.18, <2.00",
    ],
    extras_require=extras_require,
    python_requires=">=3.10, <4",
)
