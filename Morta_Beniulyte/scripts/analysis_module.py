from decimal import Decimal
from constant import CONFIG

def make_mean_table(file_name):

    """Creates a dictionary where each sample has its own dictionary where gene names are keys and mean Ct value is the value"""

    with open(file_name, "r") as file:
        lines = file.read().splitlines()

    mean_table = {}

    for line in lines[8:]:
        data = line.split(",")

        if not data[0]:
            break

        sample_name = data[1]
        gene_name = data[2]
        mean = Decimal(data[10])

        if sample_name not in mean_table:
            mean_table[sample_name] = {}

        if gene_name not in mean_table[sample_name]:
            if gene_name == 
            mean_table[sample_name][gene_name] = mean

    return mean_table

def make_mean_minus_hk_table(mean_table, housekeeping_gene):  

    """ Creates a dictionary where each sample has its own dictionary where gene names are keys and difference between Ct value of the gene and Ct 
    value of the chosen housekeeping gene"""
    
    mean_table_minus_hk_gene = {}

    for sample in list(mean_table.keys()):

        mean_table_minus_hk_gene[sample] = {}

        for gene in mean_table[sample]:
                
            if gene == housekeeping_gene:
                continue
            else:
                mean_table_minus_hk_gene[sample][gene] = mean_table[sample][gene] - mean_table[sample][housekeeping_gene]

    return mean_table_minus_hk_gene

def make_deldel_Ct_table(mean_table_minus_hk_gene, cntrl_sample):
    
    deldel_Ct_table = {}   

    for sample in list(mean_table_minus_hk_gene.keys()):

        if sample != cntrl_sample:
            deldel_Ct_table[sample] = {}

            for gene in mean_table_minus_hk_gene[sample]:
                 deldel_Ct_table[sample][gene] = mean_table_minus_hk_gene[sample][gene] - mean_table_minus_hk_gene[cntrl_sample][gene]

    return deldel_Ct_table

def make_results_relative_uni_table(deldel_Ct_table):

    relative_table = {}

    for sample in list(deldel_Ct_table.keys()):
        relative_table[sample] = {}
        
        for gene in deldel_Ct_table[sample]:
            number = 2 ** -(deldel_Ct_table[sample][gene])
            relative_table[sample][gene] = number.quantize(Decimal("0.00000001"))

    return  relative_table