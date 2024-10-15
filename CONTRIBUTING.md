## Contributing to this Repository
Welcome ! We greatly appreciate your interest in contributing to our project. Please follow the guidelines below to ensure a smooth and successful contribution process.

## Fork the Repository
To get started, fork the dstoolkit-text2sql-and-imageprocessing
 main repository to your own GitHub account by clicking on the "Fork" button at the top right corner of the repository page. This will create a copy of the repository under your account, which you can freely make changes to.

## Clone the Repository
Next, clone the forked repository to your local machine using the following command:

```
git clone https://github.com/[your-github-username]/[your-repository-name].git
```

Make sure to replace [your-github-username] with your actual GitHub username and [your-repository-name] with the name of your forked repository.

## Set Up Access to Relevant Services
Please ensure that you have the appropriate permissions and credentials to avoid any issues during the contribution process. This includes Azure DevOps project, repository, pipelines and Azure Subscription.  

## Install Dependencies and Validate Environment
Before making changes, ensure that you have installed all the dependencies required for the project. This include Conda, Python 3.8 (ideal) and tools. Validate that your development environment is set up correctly and meets the project's requirements.

## Create a Branch
Create a new branch for your contribution. It's important to create a new branch for each contribution to keep the main branch clean and stable. You can create a new branch using the following command:
```
git checkout -b [branch-name]
```

Replace [branch-name] with a descriptive name for your branch that indicates the purpose of your contribution.

## Make Changes
Now it's time to make your changes! Follow the coding style and guidelines of the project, and thoroughly test your changes in your local environment. Ensure that your changes do not introduce any errors or break the existing functionality. Be sure to add appropriate comments and documentation as needed.

## Validate code changes
Before submitting your contribution, it's crucial to validate your changes by building and testing the project on your environment. This includes running code quality checks, linting, unit tests including training scripts, executing tests, or other validation processes. Make sure that your changes do not cause any build failures or test errors. 

## Commit and Push Changes
Once you're confident with your changes, commit your changes and push them to your forked repository using the following commands:

```
git add .
git commit -m "Your commit message here"
git push origin [branch-name]
```
Replace [branch-name] with the name of your branch.

## Create a Pull Request
Go to the original [Your Repository Name] repository on GitHub and click on the "New Pull Request" button. Select your branch from the base and compare branches drop-down menus. Review your changes and provide a descriptive title and detailed description for your pull request. Include relevant information, such as the purpose of your contribution, the changes made, and any necessary context. Click on the "Create Pull Request" button to submit your contribution.

## Validate Builds and Tests
After PR is created, build validation must pass before the code can be merged on the target develop branch. Any feedback from build validation must be addressed or else the PR will not get merged to target develop branch. 

## Review and Address Feedback
Your pull request will be reviewed by the repository maintainers, and they may provide feedback or request changes. Be sure to monitor your pull request and address any feedback in a timely manner. This may involve making additional changes, providing clarification, or addressing any issues raised during the review process.

## Follow Code of Conduct
As a contributor, it's important to adhere to the project's code of conduct. Make sure to follow the project's guidelines, respect the contributions of others, and avoid any inappropriate behavior. Additionally, ensure that your contribution does not violate any copyright or intellectual property rights.

## Merge and Close
Once your contribution has been approved and all feedback has been addressed, you should merge your changes into the develop branch. After the changes have been merged, your contribution will be credited and acknowledged in the project's documentation or contributors list. Your pull request will then be closed, and your contribution will become part of the project's codebase.

Congratulations! You have successfully contributed to dstoolkit-text2sql-and-imageprocessing. Thank you for your valuable contribution and for following the contribution guidelines.

If you have any questions or need further assistance, feel free to reach out to the repository maintainers or the project's team channel for support.

Happy contributing!

## Contributing

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.opensource.microsoft.com.

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.
