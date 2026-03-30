from setuptools import find_packages, setup

setup(
    name="control-fabric",
    version="1.0.0",
    packages=find_packages(),
    install_requires=["httpx>=0.27.0"],
    python_requires=">=3.11",
    description="Control Fabric Platform Python SDK",
    long_description="Python SDK for the Control-Native Decision Platform",
)
