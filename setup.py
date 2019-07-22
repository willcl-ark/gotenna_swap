import setuptools

# with open("README.md", "r") as fh:
#     long_description = fh.read()

setuptools.setup(
    name="go-sat-sub",
    version="0.0.2",
    author="Will Clark",
    author_email="will8clark@gmail.com",
    description="upload a message to Blockstream Blocksat, paying lightning invoice using a"
    " submarine swap",
    # long_description=long_description,
    # long_description_content_type="text/markdown",
    url="https://github.com/willcl-ark/go-sat-sub",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3.6",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    keywords="gotenna submarine blockstream satellite swap",
    install_requires=[],
    python_requires=">=3.6",
)
