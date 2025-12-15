# Project Title

A short 1–2 line description of what this project does.

---

## 📁 File Structure

```bash
project-root/
│
├── codes/ # Core source code
│ ├── pdf_to_latex # Entry point of the application
  │ ├── script.py # main file

```


---

## How to Run

### Main Pipeline

#### 0.(Optional) Create a Version:
```folder path -> codes/pdf_to_latex/```

run command : ``` python version_control/create_version.py --name "v1.0.0" ```


#### 1. Create a config file:
```folder path -> codes/pdf_to_latex/config```

Create a config file here for the book you want to run here.

Example Config:
```
{
    "book": "../../files/ai/inputs/ai.pdf",
    "tex": "../../files/ai/inputs/ai.tex",
    "bib": "../../files/ai/inputs/ai_bib.pdf",
    "index": "../../files/ai/inputs/ai_index.pdf",
    "batch_size": 600,
    "sequential": false,
    "skip": [],
    "chapter_level": 3,
    "section_level": 4,
    "subsection_level": 5,
    "use_bib_cache": true,
}
```

#### 2. Run the main ```script.py```
```folder path -> codes/pdf_to_latex/script.py```

run command : ``` python script.py --config "configs/<config_name>.json" ```

Optional, add skip parameter at the end to skip desired steps ```--skip 2 3 5 ``` ( this will skip steps 2 3 and 5)

The outputs will be stored in 
```files/<book_name>/<version_name>```



### Testing Pipeline

```tests/regression_test/```

#### 1. run for the current version
run script : ``` python main.py ai algorithms assembly cybersec data-science ( book names space seperated) --scoring-method multi-metric ```

#### 2. rerun for all the versions.
Generally when there will be a change in test metrics or the excel registry, the excel results file will be deleted and you can run the test on all the versions from beginning

run script : ```python run_all.py```

runs the 1st script for all versions for the 5 books ( hard coded  (need to change)) 
