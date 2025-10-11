#!/usr/bin/env python3
"""
PDF to LaTeX Regression Testing Main Script

Usage:
    python main.py ai physics chemistry --scoring-method similarity --output-dir results
    python main.py --all --scoring-method comprehensive

File Structure Expected:
    files/
    ├── ai/
    │   ├── inputs/ai.tex
    │   └── <version>/ai_final.tex
    ├── physics/
    │   ├── inputs/physics.tex
    │   └── <version>/physics_final.tex
    tests/
    └── regression_test/
        ├── main.py (this file)
        ├── scores/
        │   ├── similarity.py
        │   └── comprehensive.py
        └── results/
"""

import argparse
import sys
import os
import importlib
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import logging
import csv
from pathlib import Path
import importlib.util
import os


# Robust import for excel_registry:
# - Prefer package-relative import when running as module
# - Fall back to loading the file by path when running main.py directly
try:
    from .excel_registry import update_master_excel
except Exception:
    try:
        # Try to load module from the same directory as this script
        here = Path(__file__).resolve().parent
        registry_path = here / "excel_registry.py"
        spec = importlib.util.spec_from_file_location("excel_registry", str(registry_path))
        excel_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(excel_mod)
        update_master_excel = excel_mod.update_master_excel
    except Exception:
        # Final fallback: leave a stub that warns when called
        def update_master_excel(results_dir, book_name, result):
            logger = __import__("logging").getLogger(__name__)
            logger.warning("excel_registry unavailable; skipping master excel update")

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class RegressionTester:
    def __init__(self, scoring_method: str = "similarity", output_dir: str = "results"):
        # Get the test directory (where this main.py is located)
        self.test_dir = Path(__file__).parent

        # Book files are in the files directory (two levels up from tests/regression_test/)
        self.files_dir = self.test_dir.parent.parent / "files"

        # Scoring modules are in the scores subdirectory
        self.scores_dir = self.test_dir / "scores"

        # Results go in the specified output directory within test directory
        self.results_dir = self.test_dir / output_dir
        self.results_dir.mkdir(exist_ok=True)
        # Current version subdirectory (if any)
        self.current_version = self.get_current_version_name()

        # Load scoring function
        self.scoring_function = self._load_scoring_function(scoring_method)
        self.scoring_method = scoring_method

        logger.info(f"Files directory: {self.files_dir}")
        logger.info(f"Results directory: {self.results_dir}")
        logger.info(f"Using current version: {self.current_version or 'legacy outputs/'}")
        logger.info(f"Using scoring method: {scoring_method}")


    def get_current_version_name(self):
        """
        Get the current version name from version control.
        Returns the name of the currently active version.
        If no version is found or version control is not initialized,
        returns 'original' as the default.
        """
        # Directly read the version_history.json file in the project's version_control
        try:
            repo_root = self.test_dir.parent.parent
            vh_path = repo_root / "codes" / "pdf_to_latex" / "version_control" / "version_history.json"
            if not vh_path.exists():
                logger.warning(f"version_history.json not found at {vh_path}; using 'original'")
                return "original"

            with open(vh_path, "r", encoding="utf-8") as f:
                versions = json.load(f)

            # versions is expected to be a list of version entries
            for v in versions:
                if isinstance(v, dict) and v.get("is_current"):
                    name = v.get("name")
                    logger.info(f"Detected current version from JSON: {name}")
                    return name or "original"

            logger.warning("No version marked is_current in version_history.json; using 'original'")
            return "original"
        except Exception as e:
            logger.warning(f"Error reading version_history.json ({e}); using 'original'")
            return "original"


    def _load_scoring_function(self, method_name: str):
        """Dynamically load scoring function from scores/{method_name}.py"""
        try:
            # Add scores directory to path
            sys.path.insert(0, str(self.scores_dir))

            # Import the scoring module
            scoring_module = importlib.import_module(method_name)

            # Get the scoring function (assume it's named 'calculate_score')
            if hasattr(scoring_module, "calculate_score"):
                logger.info(f"Loaded scoring method: {method_name}")
                return scoring_module.calculate_score
            else:
                raise AttributeError(
                    f"No 'calculate_score' function found in {method_name}.py"
                )

        except ImportError as e:
            logger.error(f"Failed to import scoring method '{method_name}': {e}")
            logger.error(f"Make sure {self.scores_dir}/{method_name}.py exists")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Error loading scoring function: {e}")
            sys.exit(1)

    def _validate_book_files(self, book_name: str) -> Tuple[bool, str, str]:
        """Validate that required book files exist"""
        book_dir = self.files_dir / book_name
        input_file = book_dir / "inputs" / f"{book_name}.tex"
        # Use the version-specific directory for outputs
        version_dir = book_dir / (self.current_version or "")
        output_file = version_dir / f"{book_name}_final.tex"

        errors = []
        if not book_dir.exists():
            errors.append(f"Book directory not found: {book_dir}")
        if not input_file.exists():
            errors.append(f"Input file not found: {input_file}")
        if not output_file.exists():
            errors.append(f"Output file not found: {output_file}")

        if errors:
            for error in errors:
                logger.error(error)
            return False, str(input_file), str(output_file)
        
        # We no longer create per-book CSV files; results are written only to the master Excel.

        return True, str(input_file), str(output_file)

    def _book_version_dir(self, book_name: str) -> Path:
        """Return path to the book's current-version directory."""
        return self.files_dir / book_name / (self.current_version or "")

    def discover_books(self) -> List[str]:
        """Discover all available books in the files directory"""
        if not self.files_dir.exists():
            logger.error(f"Files directory does not exist: {self.files_dir}")
            return []

        books = []
        for item in self.files_dir.iterdir():
            if item.is_dir():
                # Check if it has the expected structure
                input_file = item / "inputs" / f"{item.name}.tex"
                # Only consider the current-version directory (no fallback to outputs/)
                version_dir = item / (self.current_version or "")
                output_file = version_dir / f"{item.name}_final.tex"
                if input_file.exists():
                    books.append(item.name)
                else:
                    logger.info(f"Skipping {item.name}: no input book for version '{self.current_version}'")

        logger.info(f"Discovered {len(books)} books: {books}")
        return sorted(books)

    def test_book(self, book_name: str) -> Dict:
        """Test a single book and return results"""
        logger.info(f"Testing book: {book_name}")

        # Validate files exist
        valid, input_file, output_file = self._validate_book_files(book_name)

        result = {
            "book_name": book_name,
            "input_file": input_file,
            "output_file": output_file,
            "scoring_method": self.scoring_method,
            "timestamp": datetime.now().isoformat(),
            "valid": valid,
        }

        if not valid:
            result.update(
                {
                    "score": 0.0,
                    "error": f"Missing files for book: {book_name}",
                    "details": {},
                }
            )
            return result

        try:
            # Call the scoring function
            score_result = self.scoring_function(input_file, output_file)

            # Handle different return types from scoring functions
            if isinstance(score_result, (int, float)):
                result.update(
                    {"score": float(score_result), "details": {}, "error": None}
                )
            elif isinstance(score_result, dict):
                result.update(
                    {
                        "score": float(score_result.get("score", 0.0)),
                        "details": score_result,
                        "error": None,
                    }
                )
            else:
                raise ValueError(
                    f"Unexpected return type from scoring function: {type(score_result)}"
                )

            logger.info(f"Book {book_name} scored: {result['score']:.2f}")

        except Exception as e:
            result.update({"score": 0.0, "error": str(e), "details": {}})
            logger.error(f"Error scoring book {book_name}: {e}")

        return result

    def test_multiple_books(self, book_names: List[str]) -> List[Dict]:
        """Test multiple books and return results"""
        results = []

        logger.info(
            f"Testing {len(book_names)} books with scoring method: {self.scoring_method}"
        )

        for book_name in book_names:
            result = self.test_book(book_name)
            # Only append and update master excel for valid results (i.e., version dir and files present)
            if result.get("valid"):
                self.append_to_csv(book_name, result)
            else:
                logger.info(f"Skipping CSV/master update for {book_name} (invalid or missing version folder)")

            results.append(result)

        return results
    
    def append_to_csv(self, book_name: str, result: Dict) -> None:
        """Record book result in the master Excel only (no per-book CSVs).

        If the book doesn't have the current-version directory, the update is skipped
        and a message is logged.
        """
        version_dir = self._book_version_dir(book_name)

        if not version_dir.exists():
            logger.error(f"Skipping master update: version directory not found for {book_name}: {version_dir}")
            return

        try:
            results_dir = Path(self.test_dir) / "results"
            results_dir.mkdir(exist_ok=True)
            update_master_excel(results_dir, book_name, result)
            logger.info(f"Updated master excel with results for {book_name}")
        except Exception as e:
            logger.error(f"Failed to update master excel for {book_name}: {e}")

    def save_results(self, results: List[Dict], filename: str = None) -> str:
        """Save results to JSON file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"regression_results_{self.scoring_method}_{timestamp}.json"

        results_file = self.results_dir / filename

        summary = {
            "scoring_method": self.scoring_method,
            "timestamp": datetime.now().isoformat(),
            "total_books": len(results),
            "valid_books": len([r for r in results if r["valid"]]),
            "average_score": (
                sum(r["score"] for r in results) / len(results) if results else 0
            ),
            "results": results,
        }

        with open(results_file, "w") as f:
            json.dump(summary, f, indent=2)

        logger.info(f"Results saved to: {results_file}")
        return str(results_file)

    def plot_results(self, results: List[Dict], save_plot: bool = True) -> str:
        """Create and save a plot of the scores"""
        # Filter valid results for plotting
        valid_results = [r for r in results if r["valid"] and r["score"] > 0]

        if not valid_results:
            logger.warning("No valid results to plot")
            return None

        # Extract data for plotting
        book_names = [r["book_name"] for r in valid_results]
        scores = [r["score"] for r in valid_results]

        # Create the plot
        plt.figure(figsize=(12, 6))

        # Create bar plot
        bars = plt.bar(book_names, scores, color="skyblue", edgecolor="navy", alpha=0.7)

        # Customize the plot
        plt.title(
            f"Book Scores - {self.scoring_method.title()} Method",
            fontsize=16,
            fontweight="bold",
        )
        plt.xlabel("Books", fontsize=12)
        plt.ylabel("Score", fontsize=12)
        plt.ylim(0, 100)

        # Add score labels on bars
        for bar, score in zip(bars, scores):
            height = bar.get_height()
            plt.text(
                bar.get_x() + bar.get_width() / 2.0,
                height + 1,
                f"{score:.1f}",
                ha="center",
                va="bottom",
                fontweight="bold",
            )

        # Add horizontal line for average
        avg_score = sum(scores) / len(scores)
        plt.axhline(
            y=avg_score,
            color="red",
            linestyle="--",
            alpha=0.7,
            label=f"Average: {avg_score:.1f}",
        )

        # Rotate x-axis labels if there are many books
        if len(book_names) > 5:
            plt.xticks(rotation=45, ha="right")

        plt.legend()
        plt.tight_layout()
        plt.grid(axis="y", alpha=0.3)

        if save_plot:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            plot_filename = f"scores_plot_{self.scoring_method}_{timestamp}.png"
            plot_path = self.results_dir / plot_filename
            plt.savefig(plot_path, dpi=300, bbox_inches="tight")
            logger.info(f"Plot saved to: {plot_path}")

            plt.show()
            return str(plot_path)
        else:
            plt.show()
            return None


def main():
    parser = argparse.ArgumentParser(description="PDF to LaTeX Regression Testing")
    parser.add_argument("books", nargs="*", help="Book names to test")
    parser.add_argument("--all", action="store_true", help="Test all discovered books")
    parser.add_argument(
        "--scoring-method",
        default="diff",
        help="Scoring method to use (default: diff)",
    )
    parser.add_argument(
        "--output-dir",
        default="results",
        help="Output directory for results (default: results)",
    )
    parser.add_argument(
        "--list-books", action="store_true", help="List all available books and exit"
    )
    parser.add_argument("--no-plot", action="store_true", help="Skip plotting results")

    args = parser.parse_args()

    # Initialize tester
    tester = RegressionTester(
        scoring_method=args.scoring_method, output_dir=args.output_dir
    )

    # Handle list books command
    if args.list_books:
        books = tester.discover_books()
        print(f"Available books ({len(books)}):")
        for book in books:
            print(f"  - {book}")
        return

    # Determine which books to test
    if args.all:
        book_names = tester.discover_books()
        if not book_names:
            logger.error("No books found to test")
            sys.exit(1)
    elif args.books:
        book_names = args.books
    else:
        parser.print_help()
        sys.exit(1)

    # Run tests
    logger.info(f"Starting regression tests for {len(book_names)} books")
    results = tester.test_multiple_books(book_names)

    # Save results
    results_file = tester.save_results(results)

    # Create and save plot
    if not args.no_plot:
        plot_file = tester.plot_results(results, save_plot=True)

    # Print summary
    valid_results = [r for r in results if r["valid"]]
    avg_score = (
        sum(r["score"] for r in valid_results) / len(valid_results)
        if valid_results
        else 0
    )

    print(f"\n{'='*50}")
    print(f"REGRESSION TEST SUMMARY")
    print(f"{'='*50}")
    print(f"Scoring Method: {args.scoring_method}")
    print(f"Total Books: {len(results)}")
    print(f"Valid Books: {len(valid_results)}")
    print(f"Average Score: {avg_score:.2f}")
    print(f"Results saved to: {results_file}")
    if not args.no_plot:
        print(f"Plot saved to: {plot_file}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
