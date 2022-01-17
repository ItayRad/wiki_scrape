import sys
import os
import logging
import traceback
from logging.handlers import RotatingFileHandler

import requests
from bs4 import BeautifulSoup

import constants


# initialize LOGGER library
logger = logging.getLogger("Rotating Log")
logger.setLevel(logging.INFO)
formatter = logging.Formatter(constants.LOGGER_FORMAT)
handler = RotatingFileHandler(
    constants.LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=3)
handler2 = logging.StreamHandler(sys.stdout)

handler.setFormatter(formatter)
handler2.setFormatter(formatter)

logger.addHandler(handler)
logger.addHandler(handler2)


def get_wiki_page_html(url):
    """
    Sends get requests to url
    return html content
    """
    logger.info(f'Sending get request to url {url}')
    try:
        resp = requests.get(url)
        return resp.text

    except Exception:
        # If something's wrong with connection, return None
        logger.error('Error connecting to URL')
        logger.error(traceback.format_exc())

    return None


def get_soup_of_animals_table(html_content):
    """
    Gets full HTML page as text
    return table soup
    """
    soup = BeautifulSoup(html_content, 'lxml')
    table = soup.select_one(constants.TABLE_SELECTOR_PATH)
    return table


def add_row_data_to_mapping(mapping, adj_list, animal_name):
    """
    gets adjective and animal name
    adds the animal name to the adjective that he represents
    """
    for col_adj in adj_list:
        col_adj = col_adj.strip()
        if mapping.get(col_adj) is None:
            mapping[col_adj] = []
        mapping[col_adj].append(animal_name)

    return mapping


def iterate_over_table_and_fill_mapping(table):
    """
    gets the animal table, adds animal and adjective to the dictionary
    """
    mapping = {}
    tbody = table.find('tbody')
    all_tr = tbody.find_all('tr')
    # init column index values
    animals_column_index = -1
    col_adj_column_index = -1
    # Runs in all the table
    for i, current_tr in enumerate(all_tr):
        # ONLY on table header, find the index which contains Animals and index of col_adj
        if i == 0:
            for j, col in enumerate(current_tr):
                if col.text == 'Animal':
                    animals_column_index = j
                if col.text == 'Collateral adjective':
                    col_adj_column_index = j
            # if one of the indexes didnt change from -1 there is an error and the loop breaks
            if animals_column_index < 0 or col_adj_column_index < 0:
                logger.error(
                    'Could not find animals and collateral adjective column names')
                exit(1)

            # because we dont want the header to get inside our dictionary..
            continue

        # We want to skip rows which indicate new letter such as 'A', 'B', etc..
        if len(current_tr.contents) < 3:
            continue

        # clean names from special letters such as ';' ',' and whitespaces
        animal_name = extract_animal_names(
            current_tr.contents, animals_column_index)

        col_adj = current_tr.contents[col_adj_column_index].text

        # clean adj
        col_adj = extract_animal_adj(col_adj)

        mapping = add_row_data_to_mapping(mapping, col_adj, animal_name)
        mapping = add_picture_path_to_map(mapping, col_adj, animal_name)
        img_url = get_img_url_path(current_tr.contents, animals_column_index)
        img_animal_page = get_img_from_animal_page(animal_name, img_url)
        image_downloader(animal_name, img_animal_page)

    return mapping


def extract_animal_adj(col_adj):
    """
    gets animal adj
    fixes animal collateral adjective without special letters and spaces
    returns list of all col adjectives
    """
    if (col_adj == '?'):
        col_adj = 'unknown'
    if (col_adj == ''):
        col_adj = 'none'
        # clean from special characters and if there is 2 or more col adjectives take them all,

    col_adj = col_adj.strip().split('/', 1)[0].split('[', 1)[0].split(" ")
    return col_adj


def extract_animal_names(current_tr, animals_column_index):
    """
    gets current table row and the animals column index
    returns the animal name that founds ithin the a tag, deletes everything after the / if it exists
    """
    animal_name = current_tr[animals_column_index].find(
        'a').text.split('/')[0]
    return animal_name


def get_img_url_path(current_tr, animals_column_index):
    """
    gets current table row and the animals column index
    returns the animal direct link to wiki page
    """
    animal_name = current_tr[animals_column_index].find('a')['href']
    return constants.DEFAULT_WIKI_PAGE + animal_name


def print_mapping(mapping):
    """
    prints out all Animals and their Collateral Adjectives from the dictionary
    """
    # for k, v in mapping.items():
    #     if (len(v) > 1):
    #         logger.info(
    #             f'Collateral Adjective: {k}, Animals: {v[0]}, Picture Path: {v[1]}')
    for k, v in mapping.items():
        if (len(v) > 1):
            logger.info(f'Collateral Adjective: {k}, Animals: {v}')


def add_picture_path_to_map(mapping, col_list, animal_name):
    """
    gets 2 parameters and adds to the dictionary, check if adj is empty it will initiate one
    """
    path = (constants.SAVE_IMG_DIRECTORY +
            animal_name + constants.IMG_FILE_EXTENSION)
    # dont need to check validation because we checked it before
    for col_adj in col_list:
        col_adj = col_adj.strip()
        mapping[col_adj].append(path)
    return mapping


def get_img_from_animal_page(animal_name, img_url):
    """
    gets the specific name of the animal
    returns the image url of the animal
    """
    resp = get_wiki_page_html(img_url)  # returns html text
    if resp is None:
        logger.error(f'Could not download image of {animal_name}')
        return

    soup = BeautifulSoup(resp, 'lxml')

    # Trying to get the image by 1 way

    found_image = soup.select_one(
        constants.FIND_ANIMAL_IMAGE)
    if found_image is not None:
        found_image = found_image['src']
    elif found_image is None or found_image == '':
        # Alternative way to get the image if first fails
        found_image = soup.select_one('div:nth-child(5) div a img')['src']
    else:
        logger.error('Could not find image. please check URL')
        return None  # so it continues without downloading anything without stopping the whole process

    return 'http:' + found_image  # returns url/src as string


def make_sure_path_exists(path):
    """
    checks if path / folder exists
    if not, creates one
    """
    os.makedirs(path, exist_ok=True)


def image_downloader(animal_name, img_url):
    """
    gets the specific name of the animal
    downloads specific animal image,
    uses get_img_url function
    """
    # choose local path
    make_sure_path_exists(constants.SAVE_IMG_DIRECTORY)

    local_path = constants.SAVE_IMG_DIRECTORY + \
        animal_name + constants.IMG_FILE_EXTENSION
    logger.info(f'Preparing to download {img_url}')
    if (img_url is not None and img_url != ''):
        try:
            # reads the picture url and saves locally
            pic = requests.get(img_url)
            with open(local_path, 'wb') as file:
                file.write(pic.content)
            logger.info(f'Succesfully Downloaded picture of {animal_name}')

        except Exception:  # logs an error if there is a problem probably with the url
            logger.error('Unable to save image')
            logger.error(traceback.format_exc())
    else:
        logger.error(f'Failed to download image for {animal_name}')


def dict_to_table(mapping):
    """
    gets our mapping variable
    turns our mapping variable from dictionary to HTML table
    """
    table = '<table ><tr><td>Collateral Adjective:</td><td>Animals</td><td>Picture Path</td>'
    for k, v in mapping.items():
        table += '<tr><td>'  # creates the table and adds the key and value from mapping
        table += f'{k}</td><td>{v}'
        table += '</td></tr>'
    table += '</table>'
    return table


def export_html(mapping):
    """
    exports our mapping variable output it HTML file
    """
    logger.info('Attempting to export to HTML')
    with open('index.html', 'w') as file:
        file.write(dict_to_table(mapping))  # outputs the table to html file
    logger.info('Succesfully exported to HTML')


def main():
    html_content = get_wiki_page_html(constants.WIKI_URL)
    if html_content is None or html_content == '':
        logger.error('Cloud not fetch content from web page')
        exit(1)
    animals_table_soup = get_soup_of_animals_table(html_content)

    mapping = iterate_over_table_and_fill_mapping(animals_table_soup)
    print_mapping(mapping)
    export_html(mapping)


if __name__ == '__main__':
    main()
