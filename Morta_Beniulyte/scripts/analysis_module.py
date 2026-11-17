from decimal import Decimal

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

def make_results_table(mean_table_minus_hk_gene, cntrl_sample):
    
    results_table = {}   

    for sample in list(mean_table_minus_hk_gene.keys()):

        if sample != cntrl_sample:

            results_table[sample] = {}

            for gene in mean_table_minus_hk_gene[sample]:
                 results_table[sample][gene] = mean_table_minus_hk_gene[sample][gene] - mean_table_minus_hk_gene[cntrl_sample][gene]

    return results_table