import requests_cache
import re
import logging
from tqdm import tqdm
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from collections import defaultdict

from constants import BASE_DIR, MAIN_DOC_URL, MAIN_URL_PEP, EXPECTED_STATUS
from outputs import control_output, file_output
from configs import configure_argument_parser, configure_logging
from utils import get_response, find_tag


def whats_new(session):
    whats_new_url = urljoin(MAIN_DOC_URL, 'whatsnew/')
    responce = get_response(session, whats_new_url)
    if responce is None:
        return
    soup = BeautifulSoup(responce.text, features='lxml')
    main_div = find_tag(soup, 'section', attrs={'id': 'what-s-new-in-python'})
    div_with_url = find_tag(
        main_div, 'div', attrs={'class': 'toctree-wrapper'}
    )
    sections = div_with_url.find_all('li', attrs={'class': 'toctree-l1'})
    results = [('Ссылка на статью', 'Заголовок', 'Редактор, автор')]
    for section in tqdm(sections):
        version_a_tag = find_tag(section, 'a')
        href = version_a_tag['href']
        version_link = urljoin(whats_new_url, href)
        responce = get_response(session, version_link)
        if responce is None:
            continue
        soup = BeautifulSoup(responce.text, features='lxml')
        h1 = find_tag(soup, 'h1')
        dl = find_tag(soup, 'dl')
        results.append((version_link, h1.text, dl.text.replace('\n', ' ')))
    return results


def latest_versions(session):
    responce = get_response(session, MAIN_DOC_URL)
    if responce is None:
        return
    soup = BeautifulSoup(responce.text, features='lxml')

    sidebar = find_tag(soup, 'div', attrs={'class': 'sphinxsidebarwrapper'})
    ul_tags = sidebar.find_all('ul')
    for ul in ul_tags:
        if 'All versions' in ul.text:
            a_tags = ul.find_all('a')
            break
    else:
        raise Exception('Ничего не нашлось')
    results = [('Ссылка на документацию', 'Версия', 'Статус')]
    pattern = r'Python (?P<version>\d\.\d+) \((?P<status>.*)\)'
    for a_tag in a_tags:
        link = a_tag['href']
        text_match = re.search(pattern, a_tag.text)
        if text_match is not None:
            version, status = text_match.groups()
        else:
            version, status = a_tag.text, ''
        results.append(
            (link, version, status)
        )
    return results


def download(session):
    downloads_url = urljoin(MAIN_DOC_URL, 'download.html')
    download_dir = BASE_DIR / 'downloads'
    download_dir.mkdir(exist_ok=True)
    responce = get_response(session, downloads_url)
    if responce is None:
        return

    soup = BeautifulSoup(responce.text, features='lxml')
    main_tag = find_tag(soup, 'div', {'role': 'main'})
    table_tag = find_tag(main_tag, 'table', {'class': 'docutils'})
    pdf_a4_tag = find_tag(
        table_tag, 'a', {'href': re.compile(r'.+pdf-a4\.zip$')}
    )
    archive_link = urljoin(downloads_url, pdf_a4_tag['href'])
    filename = archive_link.split('/')[-1]
    archive_path = download_dir / filename
    file_d = get_response(session, archive_link)
    if file_d is None:
        return
    with open(archive_path, 'wb') as file:
        file.write(file_d.content)
    logging.info(f'Архив был скачан и сохранён: {archive_path}')


def pep(session):
    log = []
    response = get_response(session, MAIN_URL_PEP)
    if response is None:
        return
    soup = BeautifulSoup(response.text, 'lxml')
    results = [('Статус', 'Количество')]
    results_dict = defaultdict(int)
    section_tag = find_tag(soup, 'section', attrs={'id': 'numerical-index'})
    tbody = find_tag(section_tag, 'tbody')
    rows = tbody.find_all('tr')
    for row_tag in rows:
        status_tag = find_tag(row_tag, 'td')
        status_table = status_tag.text[1:]
        link_tag = find_tag(
            row_tag, 'a', attrs={'href': re.compile(r'pep.+')}
        )
        href = link_tag['href']
        detail_pep_url = urljoin(MAIN_URL_PEP, href)
        pep_response = get_response(session, detail_pep_url)
        if pep_response is None:
            return
        pep_response.encoding = 'utf-8'
        pep_soup = BeautifulSoup(pep_response.text, features='lxml')
        dl_tag = find_tag(pep_soup, 'dl')
        dt_tags = dl_tag.find_all('dt')
        for dt_tag in dt_tags:
            if 'Status' in dt_tag.text:
                status_pep = dt_tag.find_next_sibling('dd').text
                results_dict[status_pep] += 1
                if status_pep not in EXPECTED_STATUS[status_table]:
                    log.append('Несовпадающие статусы:\n'
                               f'{detail_pep_url}\n'
                               f'Статус в карточке: {status_pep}\n'
                               'Ожидаемые статусы:'
                               f'{EXPECTED_STATUS[status_table]}'
                               )
    results.extend(results_dict.items())
    results.append(('Total', sum(results_dict.values())))
    file_output(results, 'pep')
    logging.info('\n'.join(log))


MODE_TO_FUNCTION = {
    'whats-new': whats_new,
    'latest-versions': latest_versions,
    'download': download,
    'pep': pep,
}


def main():
    configure_logging()
    logging.info('Парсер запущен!')
    arg_parser = configure_argument_parser(MODE_TO_FUNCTION.keys())
    args = arg_parser.parse_args()
    logging.info(f'Аргументы командной сроки: {args}')
    session = requests_cache.CachedSession()
    if args.clear_cache:
        session.cache.clear()
    parser_mode = args.mode
    results = MODE_TO_FUNCTION[parser_mode](session)
    if results is not None:
        control_output(results, args)
    logging.info('Парсер завершил работу!')


if __name__ == '__main__':
    main()
