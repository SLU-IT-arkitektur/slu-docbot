# Generate report   

1. use kubectl port-forward to target redis instance  
2. run ``python generate_report.py``   
3. open report.html

# Run reporter locally
1. run: ``docker run --rm -it -p 5005:80 -p 2525:25 rnwood/smtp4dev``  
2. run: ``python reporter.py``  
