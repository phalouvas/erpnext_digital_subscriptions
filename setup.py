from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in digital_subscriptions/__init__.py
from digital_subscriptions import __version__ as version

setup(
	name="digital_subscriptions",
	version=version,
	description="Sell subscriptions for file download",
	author="KAINOTOMO PH LTD",
	author_email="info@kainotomo.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
