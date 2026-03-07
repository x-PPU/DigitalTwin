# PLC-ReferenceImplementation

Contains a reference implementation of how to model skills and capabilities in a PLC software. Additionally, the exchange of incoming (instructions) and outgoing (process data and events/alarms) is handled via a global variable list (GVL).

# Using `git subtree` Commands
## Overview
In this project, the libraries xPPU_Lib and Resi4MPM_Lib are located in different branches of a remote repository. By using git subtree, you can integrate these libraries into your project as needed. For instance, if your project requires the xPPU_Lib, you can bind it in using a subtree without merging the entire repository.
If you make changes to the library in this project and want to share these changes with all other projects using the same subtree, you can push those changes back to the original library using the git subtree push command (explained below).
If you want to get the latest version of the library, you ca    n pull the newest changes from the remote repository using the git subtree pull command.
## Commands
### 1. Add Subtree
To add a subtree, use the following commands. The `--prefix` option specifies the directory where the subtree will be placed, and `--squash` combines the commits into one.
```bash
git subtree add --prefix=Resi_lib https://gitlab.lrz.de/resi4mpm/plc-referenceimplementation.git Resi4MPM_Lib --squash
```
### 2. Pull Updates from Subtree
To update the subtree with the latest changes from the remote repository:
```bash
git subtree pull --prefix=xPPU_Lib https://gitlab.lrz.de/resi4mpm/plc-referenceimplementation.git xPPU_Lib --squash
git subtree pull --prefix=Resi_lib https://gitlab.lrz.de/resi4mpm/plc-referenceimplementation.git Resi4MPM_Lib --squash
```
### 3. Push Changes to Subtree
To push changes from your project back to the subtree's remote repository:

```bash
git subtree push --prefix=xPPU_Lib https://gitlab.lrz.de/resi4mpm/plc-referenceimplementation.git xPPU_Lib
git subtree push --prefix=Resi_lib https://gitlab.lrz.de/resi4mpm/plc-referenceimplementation.git Resi4MPM_Lib
```