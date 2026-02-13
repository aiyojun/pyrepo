import sys

import setuptools

if sys.platform != "win32":
    raise RuntimeError("This package only supports Windows 10 or later")

with open("README.md", 'r', encoding='utf-8') as fp:
    readme = fp.read()

setuptools.setup(
    name="webview2",
    version="0.0.2",
    author="aiyojun",
    author_email="aiyojun@gmail.com",
    description="Build immersive applications supported by WebView2 on Windows Operation Systems",
    long_description=readme,
    long_description_content_type="text/markdown",
    url="https://github.com/aiyojun/pypi-repo",
    packages=setuptools.find_packages(),
    package_data={
        "webview2": [
            "*.dll",
            "*.html",
            "*.js",
        ]
    },
    install_requires=[
        "pywin32",
        "voxe==0.0.4",
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python :: 3",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries",
    ],
)