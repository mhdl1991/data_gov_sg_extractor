# -*- coding: utf-8 -*-
"""
Created on Tue Feb 27 20:25:38 2024

@author: lim
"""
'''
Contains Collection Class, Dataset Class, and one wrapper function for
downloading the datasets.
'''

import requests, os, json
import pandas as pd

from typing import Optional, List, Dict, Tuple, TypeVar
from dotenv import dotenv_values

import src.config as CFG


get_api_key = dotenv_values(".env")
headers = { "x-api-key": get_api_key["API_KEY"] }
pdDF = TypeVar('pandas.core.frame.DataFrame')



class Collection:
    def __init__(self, collection_id: str) -> Tuple[str, str, List[str]]:
        '''
        Parameters
        ----------
        collection_id : str
            collection id from data.gov.sg

        Returns
        -------
        Tuple[str, str, List[str]]
            collection name, last updated date, list of dataset id within
            collection.

        '''
        self.collection_id = str(collection_id)
        self.col_url_info = CFG.api['collection'] + f'/{self.collection_id}/' +\
                            CFG.api['meta']
        
        self.collection_name = None
        self.last_updated = None
        self.dataset_id_list = None
        
        self.collection_info()
                
    def collection_info(self) -> Tuple[str, str, List[str]]:
        '''
        Returns
        -------
        Tuple(str, str, List[str]
            returns the collection name, last updated date, and a list of datasetID

        '''
        json_content = requests.get(url = self.col_url_info, headers = headers).json()
        content = json_content['data']['collectionMetadata']
        
        self.collection_name = content['name']
        self.last_updated = content['lastUpdatedAt'][:10]
        self.dataset_id_list = content['childDatasets']
        
        return (self.collection_name, self.last_updated, self.dataset_id_list)
    

class Dataset:
    def __init__(self, dataset_id: str, pdf: str = 'No', csv: str = 'No', csvdir: Optional[str] = None):
        '''
        Parameters
        ----------
        dataset_id : str
            dataset id found in url
        pdf : str
            Flag to generate pandas Dataframe.
            Use 'Yes' if want to generate            
        csv : str
            Flag to generate csv for whole dataset or not.
            Use 'Yes' if want to generate
        csvdir : TYPE, optional
            csv directory name. The path will be the date and file name.

        Returns
        -------
        None.

        '''
        self.dataset_id = dataset_id
        self.url_download = CFG.api['dataset_dl'] + f'{self.dataset_id}'
        self.url_info = CFG.api['dataset'] + f'/{self.dataset_id}/' + CFG.api['meta']
        
        self.dataset_name = None
        self.last_updated = None
        self.col_info = None
        self.dataframe_data = None
        self.total_results = 0
        self.csv_final_filepath = None
        self.json_dtype_filepath = None
        
        self.dataset_info()
        
        if pdf == 'Yes':
            self.dataset_download_pdf()
            
        if csv == 'Yes':
            self.dataset_download_csv(directory=csvdir)
        
    def dataset_info(self) -> Tuple[str, str, Dict[str,List[str]]]:
        '''
        Returns
        -------
        Tuple(str, str, Dict[str:List[str]])
            returns the collection name, last updated date, a dict of column info.
            The dict will contain mapping_id, name, datatype, description, index,
            as the keys.
        '''       
        json_content = requests.get(url = self.url_info, headers = headers).json()
        
        output_txt = json.dumps( json.loads( json_content.text ) )
        # write the response to an output file
        with open("test.json", "w") as f:
            f.write(output_txt)
        
        content = json_content['data']
        content_inner = json_content['data']['columnMetadata']
        
        dataset_name = content['name']
        last_updated = content['lastUpdatedAt'][:10]
        
        col_mapping_id = content_inner['order'] # returns a list
        col_name = []
        col_datatype = []
        col_description = []
        col_index = []
        
        for x in col_mapping_id:
            col_attr = content_inner['metaMapping'][x]
            try:
                col_name.append(col_attr['name'])
            except:
                print("No column name attribute")
            try:
                col_datatype.append(col_attr['dataType'])
            except:
                print('No dataType attribute')
            try:
                col_index.append(col_attr['index'])
            except:
                print('No index attribute')
        
        col_info = {'col_mapping_id': col_mapping_id,
                    'col_name': col_name,
                    'col_datatype': col_datatype,
                    'col_description': col_description,
                    'col_index': col_index}
        
        self.dataset_name = dataset_name
        self.last_updated = last_updated
        self.col_info = col_info
        
        return (self.dataset_name, self.last_updated, self.col_info)
    
    def dataset_download_csv(self, directory=None) -> pdDF:
        '''
        Parameters
        ----------
        directory : TYPE, optional
            folder / directory where the csv file will be saved to.

        Returns
        -------
        pdf : pandas Dataframe
            Function will produce a csv file in the directory with the 
            last updated date of the dataset together with the dataset name.

        '''
        if self.dataset_name == None or self.last_updated == None:
            dataset_name, last_updated, col_info = self.dataset_info(self.dataset_id)
        
        if directory==None:
            filepath = f"{self.last_updated} {self.dataset_name}.csv"
            jsonfp = f"{self.last_updated} {self.dataset_name}_dtype.json"
        else:
            filepath = f"{directory}/{self.last_updated} {self.dataset_name}.csv"
            jsonfp = f"{directory}/{self.last_updated} {self.dataset_name}_dtype.json"
        
        self.csv_final_filepath = filepath
        self.json_dtype_filepath = jsonfp
        
        if self.dataframe_data is None:
            self.dataframe_data = self.dataset_download_pdf()
            
        self.dataframe_data.to_csv(self.csv_final_filepath, index=False)
        
        # Save the dtype to json
        self.dtype_to_json(self.dataframe_data)
        
        print(f'{self.csv_final_filepath} downloaded')
        print(f'{self.json_dtype_filepath} created')
        
        return self.dataframe_data
    
    def dataset_download_pdf(self) -> pdDF:
        '''
        Returns
        -------
        pdDF
            pd.DataFrame that contains everything
        '''
        print(f"Downloading from {self.url_download}")
        ini_json_content = requests.get(url = self.url_download, headers = headers).json()
        
        self.total_results = ini_json_content['result']['total']
        print(f'There are a total of {self.total_results} rows in this dataset')
        
        if self.total_results <= 1000:
            # dataset_download_counter() returns None for offset_end and limit if self.total_results < 1000
            # and this causes some kind of error with range() because it can't interpret NoneType as an int 
            # or at least, it doesn't anymore
            # so I'm putting this bit in as a workaround
            
            _url = self.url_download
            _json_content = requests.get(url = _url, headers = headers).json()
            _record = _json_content['result']['records']
            _record_df = pd.DataFrame(_record)
            
            print(f"Processed {self.total_results} / {self.total_results} rows.")
            self.dataframe_data = _record_df
            
        else: 
            offset_start, offset_end, limit = self.dataset_download_counter()
            
            for x in range(offset_start, offset_end, limit):
                if x == 0:
                    offset_limit_str = f"&limit={limit}"
                elif x > 0:
                    offset_limit_str = f"&offset={x}&limit={limit}"
                loop_url = self.url_download + offset_limit_str
                loop_json_content = requests.get(url = loop_url, headers = headers).json()
                loop_record = loop_json_content['result']['records']
                loop_record_df = pd.DataFrame(loop_record)
                if x == offset_start:
                    overall_loop_record_df = loop_record_df
                else:
                    overall_loop_record_df = pd.concat([overall_loop_record_df, loop_record_df], axis=0, ignore_index=True)
                if x > (offset_end-limit):
                    print(f"Processed {self.total_results} / {self.total_results} rows.")
                else:
                    print(f"Processed {x+limit} / {self.total_results} rows.")
                
            self.dataframe_data = overall_loop_record_df
            
        return self.dataframe_data
    
    def dataset_download_counter(self) -> Tuple[int, int, int]:
        '''
        Returns
        -------
        Tuple[int, int, int]
            A range to feed the for loop in dataset_download_pdf that downloads the
            whole dataset.
        '''
        if int(self.total_results) <= 1000:
            offset_end = None
            limit = None
        elif int(self.total_results) > 1000:
            offset_end = int(self.total_results) + 1
            limit = 1000
        
        return (0, offset_end, limit)
    
    def dtype_to_json(self, pdf: pdDF) -> dict:
        '''
        Parameters
        ----------
        pdf : pandas.DataFrame
            pandas.DataFrame so we can extract the dtype
            
        Returns
        -------
        Dict
            The dtype dictionary used
        
        To create a json file which stores the pandas dtype dictionary for
        use when converting back from csv to pandas.DataFrame.
        '''
        dtype_dict = pdf.dtypes.apply(lambda x: str(x)).to_dict()
        
        with open(self.json_dtype_filepath, 'w') as json_file:
            json.dump(dtype_dict, json_file)
        
        return dtype_dict
    
def dtype_to_json(pdf: pdDF, json_file_path: str) -> dict:
    '''
    Parameters
    ----------
    pdf : pandas.DataFrame
        pandas.DataFrame so we can extract the dtype
    json_file_path : str
        the json file path location
        
    Returns
    -------
    Dict
        The dtype dictionary used
    
    To create a json file which stores the pandas dtype dictionary for
    use when converting back from csv to pandas.DataFrame.
    '''
    dtype_dict = pdf.dtypes.apply(lambda x: str(x)).to_dict()
    
    with open(json_file_path, 'w') as json_file:
        json.dump(dtype_dict, json_file)
    
    return dtype_dict
      
def json_to_dtype(jsonfilepath):
    with open(jsonfilepath, 'r') as json_file:
        loaded_dict = json.load(json_file)
    return loaded_dict
    
def download_collection(collection_id: str, chk: str = 'No', combcsv: str = 'No',\
                        indcsv: str = 'No', csvdir: Optional[str] = None)\
                        -> pdDF:
    '''
    Wrapper function to download the whole collection

    Parameters
    ----------
    collection_id : str
        DESCRIPTION.
    chk : str
        Flag for whether to check csvdir for any existing csv's which are same.
        Options of 'Yes' or 'No'.
        If 'Yes', won't download csv if same last updated date.
        If 'No', wont check and will just download. Will overwrite if have existing.
    combcsv : str, optional
        Flag for whether to combine the whole collection into one csv.
    indcsv : str, optional
        Flag for whether to download individual datasets in the collection.
    csvdir : Optional[str], optional
        The place where csv are stored.
        Will check this directory if existing files are stored.
        If not, will re-download.

    Returns
    -------
    pdDF
        A combined pandas Dataframe.

    '''
    collection_object = Collection(collection_id)
    countofdataset = len(collection_object.dataset_id_list)
    print(f'Collection {collection_id} contains {countofdataset} no(s) of dataset.')
    
    combinedpdf = None
    
    if chk == 'Yes':
        ### Confirm which dataset is missing
        # Current list in directory.
        listindir = []
        for root, dirs, files in os.walk(os.getcwd()):
            for file in files:
                file_path = os.path.relpath(os.path.join(root, file), os.getcwd())
                listindir.append(file_path.replace('\\','/'))
        
        # Check for missing.
        missingdataset = []
        for x in range(countofdataset):
            # Get the current file path
            d_id = collection_object.dataset_id_list[x]
            d_obj = Dataset(d_id, 'No', 'No', csvdir)
            if csvdir==None:
                filepath = f"{d_obj.last_updated} {d_obj.dataset_name}.csv"
                jsonfp = f"{d_obj.last_updated} {d_obj.dataset_name}_dtype.json"
            else:
                filepath = f"{csvdir}/{d_obj.last_updated} {d_obj.dataset_name}.csv"
                jsonfp = f"{csvdir}/{d_obj.last_updated} {d_obj.dataset_name}_dtype.json"

            if filepath in listindir and jsonfp in listindir:
                dtypedict = json_to_dtype(jsonfp)
                if combinedpdf is None:
                    combinedpdf = pd.read_csv(filepath, dtype=dtypedict)
                else:
                    pdf_not_missing = pd.read_csv(filepath, dtype=dtypedict)
                    combinedpdf = pd.concat([combinedpdf, pdf_not_missing], axis=0, ignore_index=True)
            else:
                missingdataset.append(d_id)
            print(f'Checked {x+1} out of {countofdataset} datasets.')
                
        if len(missingdataset) == 0:
            print('All files were downloaded previously.')
        else:
            print(f'{len(missingdataset)} out of {countofdataset} datasets missing.')
            for x in range(len(missingdataset)):
                print(f'Start of Missing Dataset {x+1} out of {len(missingdataset)}')
                d_id = missingdataset[x]
                
                if indcsv == 'Yes':
                    d_obj = Dataset(d_id, 'Yes', 'Yes', csvdir)
                    
                elif indcsv == 'No':
                    d_obj = Dataset(d_id, 'Yes', 'No')
                
                if combinedpdf is None:
                    combinedpdf = d_obj.dataframe_data
                else:
                    combinedpdf = pd.concat([combinedpdf, d_obj.dataframe_data], axis=0, ignore_index=True)
                print(f'End of Missing Dataset {x+1} out of {len(missingdataset)}')
    
    elif chk == 'No':
        
        for x in range(countofdataset):
            print(f'Start of Dataset {x+1} out of {countofdataset}')
            dataset_id = collection_object.dataset_id_list[x]
            
            if indcsv == 'Yes':
                dataset_obj = Dataset(dataset_id, 'Yes', 'Yes', csvdir)
                
            elif indcsv == 'No':
                dataset_obj = Dataset(dataset_id, 'Yes', 'No')
            
            if x == 0:
                combinedpdf = dataset_obj.dataframe_data
            else:
                combinedpdf = pd.concat([combinedpdf, dataset_obj.dataframe_data], axis=0, ignore_index=True)
            print(f'End of Dataset {x+1} out of {countofdataset}')
    
    if combcsv == 'Yes':
        if countofdataset <= 1:
            print('No combination needed as there is only 1 dataset.')
        else:
            if csvdir==None:
                combcsvfilepath = f"Combined {collection_object.last_updated} {collection_object.collection_name}.csv"
                combcsvjsonfp = f"Combined {collection_object.last_updated} {collection_object.collection_name}_dtype.json"
            else:
                combcsvfilepath = f"{csvdir}/Combined {collection_object.last_updated} {collection_object.collection_name}.csv"
                combcsvjsonfp = f"{csvdir}/Combined {collection_object.last_updated} {collection_object.collection_name}_dtype.json"
    
            combinedpdf.to_csv(combcsvfilepath, index=False)
            dtype_to_json(combinedpdf, combcsvjsonfp)
            print(f'{combcsvfilepath} downloaded')
            print(f'{combcsvjsonfp} downloaded')
            
    return combinedpdf
        

