# Always use XeLaTeX instead of pdfLaTeX
$pdflatex = 'xelatex -interaction=nonstopmode -synctex=1 %O %S';

# Ensure latexmk expects PDF output
$pdf_mode = 1;

# Force compilation even if errors occur
$force_mode = 1;
