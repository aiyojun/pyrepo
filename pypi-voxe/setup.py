import setuptools

with open("README.md", 'r', encoding='utf-8') as fp:
    readme = fp.read()

setuptools.setup(
    name="voxe",
    version="0.0.4",
    author="aiyojun",
    author_email="aiyojun@gmail.com",
    description="A simple transport layer protocol",
    long_description=readme,
    long_description_content_type="text/markdown",
    url="https://github.com/aiyojun/pypi-repo",
    packages=setuptools.find_packages(),
    # install_requires=[],
    classifiers=[
        "Programming Language :: Python :: 3",
    #     "License :: OSI Approved :: MIT License",
    #     "Operating System :: OS Independent",
    ],
)