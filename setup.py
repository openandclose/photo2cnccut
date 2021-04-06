
"""photo2cnccut setup file."""

from setuptools import setup, find_packages

description = """Create g-code from photos."""

readme = description + """

See https://github.com/openandclose/photo2cnccut

License: MIT
"""

with open('VERSION') as f:
    version = f.read().strip()


setup(
    name='photo2cnccut',
    version=version,
    url='https://github.com/openandclose/photo2cnccut',
    license='MIT',
    author='Open Close',
    author_email='openandclose23@gmail.com',
    description=description,
    long_description=readme,
    classifiers=[
        'Development Status :: 4 - Beta',
        "Intended Audience :: Manufacturing",
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Topic :: Utilities',
    ],
    keywords='cnc gcode g-code image photo photovcarve rastercarve',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'photo2cnccut = photo2cnccut.ui:main',
        ],
    },
    python_requires='~=3.6',
    zip_safe=False,
)
