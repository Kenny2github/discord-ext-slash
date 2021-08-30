from re import match, S, sub
import os
from setuptools import setup

with open(os.path.join(os.path.dirname(__file__),
                       'discord', 'ext', 'slash',
                       '__init__.py'), 'r') as f:
    contents = f.read()
longdesc = match('^([\'"])\\1{2}(.*?)\\1{3}', contents, S).group(2)
version = match(r'[\s\S]*__version__[^\'"]+[\'"]([^\'"]+)[\'"]', contents).group(1)
del contents
longdesc = sub(':class:`~?([^`]+)`', r'``\1``', longdesc)

with open(os.path.join(os.path.dirname(__file__),
                       'README.rst'), 'w') as f2:
    f2.write(longdesc)

with open(os.path.join(os.path.dirname(__file__),
                       'requirements.txt'), 'r') as f3:
    requirements = f3.read().strip().splitlines()

setup(
    name="discord-ext-slash",
    version=version,
    description="Support slash commands with discord.py.",
    long_description=longdesc,
    url="https://github.com/Kenny2github/discord-ext-slash",
    author="kenny2discord",
    author_email="kenny2minecraft@gmail.com",
    license="MIT",
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Communications :: Chat',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.7',
    ],
    keywords='discord slash commands',
    packages=["discord.ext.slash"],
    install_requires=requirements,
    python_requires='>=3.7',
)
