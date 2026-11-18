import argparse
import analysis_module as pcr
import json
from pprint import pprint

parser = argparse.ArgumentParser(description = 
"Process qPCR files of experiments and biological replicates using a config file")

parser.add_argument("paths", help = "The path to JSON file which contains the paths to the datafiles")

args = parser.parse_args()

try:
        with open(args.paths, "r") as file:
                paths_json = json.load(file)
except FileNotFoundError:
        print("File not found")
        
for key in list(paths_json.keys()):

        

        mean_table = pcr.make_mean_table(paths_json[key])

        with open("../config.json", "r") as config_file:
                parameters = json.load(config_file)

        mean_table_minus_hk_gene = pcr.make_mean_minus_hk_table(mean_table, parameters["housekeeping_gene"])
        
        deldel_Ct_table = pcr.make_deldel_Ct_table(mean_table_minus_hk_gene, parameters["cntrl_sample"])

        relative_table = pcr.make_results_relative_uni_table(deldel_Ct_table)

        pprint(relative_table)

        
        #,


        
        
    
