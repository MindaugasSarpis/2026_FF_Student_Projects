import analysis_module as pcr
import json
from pprint import pprint

mean_table = pcr.make_mean_table("../data/raw/Example_Data_I.csv")

with open("../config.json") as file:
        parameters = json.load(file)

mean_table_minus_hk_gene = pcr.make_mean_minus_hk_table(mean_table, parameters["housekeeping_gene"])
       
results_table = pcr.make_results_table(mean_table_minus_hk_gene, parameters["cntrl_sample"])

pprint(results_table)
###########################
##########################
############################
############################
##############################

        
        
    
