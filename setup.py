from setuptools import setup, find_packages

setup(
    name='tools-manifest',
    version='0.1',
    author='Yuvi Panda',
    author_email='yuvipanda@gmail.com',
    packages=find_packages(),
    scripts=[
        'scripts/collector-runner',
    ],
    description='Infrastructure for running services on tools.wmflabs.org',
    install_requires=[
        'PyYAML'
    ]
)
