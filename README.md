# 2026_FF_Student_Projects

Semester projects for the data analysis course. Each student keeps their project in their own folder in this repository.

## Main requirement: the project must run

Your project has to be runnable and has to work. Someone else should be able to clone the repository, follow the instructions in your `README.md`, and run your code from start to finish without errors, getting the same results you submitted.

A project that does not run is not complete. Before you submit, test it on a fresh clone in a new environment, not only on your own setup:

```bash
git clone https://github.com/<your-username>/2026_FF_Student_Projects.git
cd 2026_FF_Student_Projects/Name_Lastname
```

Common reasons a project works for you but not for anyone else:

- a package is missing from `requirements.txt`
- the code uses absolute paths that only exist on your computer
- the data file isn't committed and there are no instructions for getting it
- notebook cells only work when run out of order (use **Restart & Run All** to check)

## What to submit

Your folder should contain:

- **Code**: scripts and/or notebooks used for the analysis.
- **Results**: figures, tables, and any other outputs your analysis produces.
- **Data**: the input data, or instructions for obtaining it if it is too large to commit (see [Data](#data)).
- **Dependencies**: a list of the packages your code needs, e.g. `requirements.txt` or `environment.yml`.
- **`README.md`**: a short description of your project (see [Project README](#project-readme)).

## Folder naming

Use one folder per student, named:

```
Name_Lastname
```

Use plain ASCII letters only, without Lithuanian diacritics (`Aidas_Krisciunas`, not `Aidas_Kriščiūnas`). Do not put files directly in the repository root; everything you submit goes inside your own folder.

## Suggested structure

```
Name_Lastname/
├── README.md
├── requirements.txt
├── data/
├── notebooks/
├── src/
└── results/
```

This layout is a suggestion, not a requirement. Use whatever fits your project, as long as it is easy to navigate.

## Project README

The `README.md` inside your folder should cover:

1. **Title and summary**: what question you are trying to answer.
2. **Data**: where the data comes from and how to get it.
3. **How to run**: the exact commands to install dependencies and reproduce your results. Use the order they must run in, if there is more than one script or notebook.
4. **Results**: a brief summary of your findings, with links to key figures or tables.

## Data

- GitHub rejects files larger than 100 MB and warns about files over 50 MB. Do not commit large datasets; link to the source or include a download script instead.
- Use relative paths (`data/measurements.csv`), not absolute ones (`C:\Users\me\Desktop\...`), so your code runs on other machines.
- Never commit passwords, API keys, or other credentials.

## How to submit

1. Fork this repository to your own GitHub account.
2. Create your `Name_Lastname` folder and add your work to it.
3. Commit and push the changes to your fork.
4. Open a pull request to this repository.

Keep your fork up to date with this repository (**Sync fork** on GitHub) before opening a pull request, and only change files inside your own folder.

## Before you submit

- [ ] The project runs from start to finish on a fresh clone in a new environment, with no errors.
- [ ] It produces the results you submitted.
- [ ] All dependencies are listed.
- [ ] Your folder has a `README.md` explaining how to run the project.
- [ ] No large data files, credentials, or temporary files (`.ipynb_checkpoints/`, `__pycache__/`, `.DS_Store`) are committed.
