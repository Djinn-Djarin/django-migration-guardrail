from setuptools import find_packages, setup


setup(
    name="django-migrations-guardrail",
    version="0.1.0",
    description="Django management commands for checking, applying, and verifying migrations.",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    packages=find_packages(include=["migration_guardrail*"]),
    python_requires=">=3.10",
    install_requires=["django>=4.1"],
    classifiers=[
        "Framework :: Django",
        "Framework :: Django :: 4.1",
        "Framework :: Django :: 4.2",
        "Framework :: Django :: 5.0",
        "Framework :: Django :: 5.1",
        "Framework :: Django :: 5.2",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
    ],
)
