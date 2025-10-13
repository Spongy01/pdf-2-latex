#!/usr/bin/env python3
"""
Integrated pipeline that runs script.py for all configs AND runs regression tests.
Combines parallel execution with comprehensive testing.
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class IntegratedPipeline:
    def __init__(self, max_workers: int = 4, scoring_method: str = "multi-metric"):
        self.max_workers = max_workers
        self.scoring_method = scoring_method
        
    def run_full_pipeline(self, config_dir: str) -> Dict:
        """Run complete pipeline: configs → testing → reporting."""
        
        print("🔄 Starting Integrated Pipeline")
        print("=" * 50)
        
        # Phase 1: Run all configs in parallel
        print("📋 Phase 1: Running all configs in parallel...")
        execution_results = self._run_parallel_configs(config_dir)
        
        if execution_results.get("failed", 0) > 0:
            print(f"⚠️  {execution_results['failed']} configs failed, but continuing with testing...")
        
        # Phase 2: Run regression tests
        print("\n🧪 Phase 2: Running regression tests...")
        test_results = self._run_regression_tests()
        
        # Phase 3: Generate comprehensive report
        print("\n📊 Phase 3: Generating comprehensive report...")
        report = self._generate_report(execution_results, test_results)
        
        return report
    
    def _run_parallel_configs(self, config_dir: str) -> Dict:
        """Run parallel execution of configs."""
        try:
            from parallel_runner import ParallelRunner
            
            runner = ParallelRunner(max_workers=self.max_workers)
            summary = runner.run_parallel(config_dir)
            
            if "error" in summary:
                logger.error(f"Parallel execution error: {summary['error']}")
                return {"error": summary["error"], "successful": 0, "failed": 0}
            
            return summary
            
        except ImportError:
            logger.error("parallel_runner.py not found")
            return {"error": "parallel_runner.py not found", "successful": 0, "failed": 0}
        except Exception as e:
            logger.error(f"Error in parallel execution: {e}")
            return {"error": str(e), "successful": 0, "failed": 0}
    
    def _run_regression_tests(self) -> Dict:
        """Run regression tests."""
        try:
            # Import regression test main
            import sys
            import os
            
            # Add tests directory to path
            test_dir = Path(__file__).parent.parent / "tests" / "regression_test"
            sys.path.insert(0, str(test_dir))
            
            from main import RegressionTester
            
            tester = RegressionTester(
                scoring_method=self.scoring_method,
                output_dir="results"
            )
            
            # Discover and test all books
            books = tester.discover_books()
            if not books:
                logger.warning("No books found for testing")
                return {"error": "No books found", "total_books": 0, "valid_books": 0, "average_score": 0}
            
            results = tester.test_multiple_books(books)
            
            # Save results
            results_file = tester.save_results(results)
            
            # Generate summary
            valid_results = [r for r in results if r["valid"]]
            avg_score = sum(r["score"] for r in valid_results) / len(valid_results) if valid_results else 0
            
            return {
                "total_books": len(results),
                "valid_books": len(valid_results),
                "average_score": avg_score,
                "results_file": results_file,
                "results": results
            }
            
        except ImportError as e:
            logger.error(f"Regression test import error: {e}")
            return {"error": f"Import error: {e}", "total_books": 0, "valid_books": 0, "average_score": 0}
        except Exception as e:
            logger.error(f"Error in regression testing: {e}")
            return {"error": str(e), "total_books": 0, "valid_books": 0, "average_score": 0}
    
    def _generate_report(self, execution_results: Dict, test_results: Dict) -> Dict:
        """Generate comprehensive report combining execution and test results."""
        
        report = {
            "pipeline_summary": {
                "execution": {
                    "total_configs": execution_results.get("total_configs", 0),
                    "successful": execution_results.get("successful", 0),
                    "failed": execution_results.get("failed", 0),
                    "total_duration": execution_results.get("total_duration", 0)
                },
                "testing": {
                    "total_books": test_results.get("total_books", 0),
                    "valid_books": test_results.get("valid_books", 0),
                    "average_score": test_results.get("average_score", 0)
                }
            },
            "execution_results": execution_results.get("results", {}),
            "test_results": test_results.get("results", []),
            "recommendations": self._generate_recommendations(execution_results, test_results),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        return report
    
    def _generate_recommendations(self, execution_results: Dict, test_results: Dict) -> List[str]:
        """Generate actionable recommendations based on results."""
        recommendations = []
        
        # Execution recommendations
        failed_configs = execution_results.get("failed", 0)
        if failed_configs > 0:
            recommendations.append(f"⚠️  {failed_configs} configs failed - check logs for details")
        
        # Test recommendations
        valid_books = test_results.get("valid_books", 0)
        total_books = test_results.get("total_books", 0)
        avg_score = test_results.get("average_score", 0)
        
        if valid_books < total_books:
            recommendations.append(f"📉 {total_books - valid_books} books failed validation - check file paths")
        
        if avg_score < 70:
            recommendations.append(f"📉 Average score ({avg_score:.1f}) is below 70 - consider pipeline improvements")
        elif avg_score > 90:
            recommendations.append(f"🎉 Excellent average score ({avg_score:.1f}) - pipeline is performing well")
        
        if not recommendations:
            recommendations.append("✅ All systems performing optimally")
        
        return recommendations
    
    def print_report(self, report: Dict):
        """Print a comprehensive report."""
        print("\n" + "=" * 60)
        print("📊 INTEGRATED PIPELINE REPORT")
        print("=" * 60)
        
        # Execution summary
        exec_summary = report["pipeline_summary"]["execution"]
        print(f"📋 Execution Results:")
        print(f"  Total Configs: {exec_summary['total_configs']}")
        print(f"  ✅ Successful: {exec_summary['successful']}")
        print(f"  ❌ Failed: {exec_summary['failed']}")
        print(f"  ⏱️  Duration: {exec_summary['total_duration']:.1f}s")
        
        # Testing summary
        test_summary = report["pipeline_summary"]["testing"]
        print(f"\n🧪 Testing Results:")
        print(f"  Total Books: {test_summary['total_books']}")
        print(f"  ✅ Valid Books: {test_summary['valid_books']}")
        print(f"  📊 Average Score: {test_summary['average_score']:.1f}")
        
        # Recommendations
        print(f"\n💡 Recommendations:")
        for rec in report["recommendations"]:
            print(f"  {rec}")
        
        print(f"\n🕒 Generated: {report['timestamp']}")
        print("=" * 60)
    
    def save_report(self, report: Dict, output_file: str = None):
        """Save comprehensive report to JSON file."""
        if output_file is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_file = f"integrated_pipeline_report_{timestamp}.json"
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"📄 Comprehensive report saved to: {output_file}")
        return output_file

def main():
    parser = argparse.ArgumentParser(
        description="Run integrated pipeline: parallel configs + regression testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python integrated_pipeline.py --config-dir configs
  python integrated_pipeline.py --config-dir configs --max-workers 2
  python integrated_pipeline.py --config-dir configs --scoring-method diff
  python integrated_pipeline.py --config-dir configs --output report.json
        """
    )
    
    parser.add_argument(
        "--config-dir",
        default="configs",
        help="Directory containing config files (default: configs)"
    )
    
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Maximum number of parallel workers (default: 4)"
    )
    
    parser.add_argument(
        "--scoring-method",
        default="multi-metric",
        choices=["diff", "similarity", "multi-metric", "comprehensive"],
        help="Regression test scoring method (default: multi-metric)"
    )
    
    parser.add_argument(
        "--output",
        help="Output file for comprehensive report (default: auto-generated)"
    )
    
    args = parser.parse_args()
    
    # Initialize pipeline
    pipeline = IntegratedPipeline(
        max_workers=args.max_workers,
        scoring_method=args.scoring_method
    )
    
    # Run full pipeline
    try:
        report = pipeline.run_full_pipeline(args.config_dir)
        
        # Print report
        pipeline.print_report(report)
        
        # Save report
        output_file = pipeline.save_report(report, args.output)
        
        # Determine exit status
        exec_failed = report["pipeline_summary"]["execution"]["failed"] > 0
        test_score_low = report["pipeline_summary"]["testing"]["average_score"] < 50
        
        if exec_failed or test_score_low:
            print("\n⚠️  Pipeline completed with issues")
            sys.exit(1)
        else:
            print("\n✅ Pipeline completed successfully")
            sys.exit(0)
            
    except KeyboardInterrupt:
        print("\n⚠️  Pipeline interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

