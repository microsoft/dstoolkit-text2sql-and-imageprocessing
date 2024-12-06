# Use the official Python image from Microsoft devcontainers
FROM mcr.microsoft.com/devcontainers/python:3

# Install ODBC drivers and dependencies
RUN apt-get update && \
    apt-get install -y apt-transport-https curl gnupg && \
    curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - && \
    curl https://packages.microsoft.com/config/debian/10/prod.list > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && \
    ACCEPT_EULA=Y apt-get install -y msodbcsql18 unixodbc-dev

# Install Azure CLI
RUN curl -sL https://aka.ms/InstallAzureCLIDeb | bash

# Set the working directory
WORKDIR /app

# Install uv package manager
RUN pip install uv
