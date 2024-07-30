# Generate report   

1. use kubectl port-forward to target redis instance  
2. run ``python generate_report.py``   
3. open report.html

# Run reporter locally (requires the chatbot to be up and running)
run: ``skaffold run -f skaffold.embeddings_updater.one.off.yaml --tail``  
open localhost:5005 in your browser to access the smtp4dev UI and see the email with the attached report (pdf)     

