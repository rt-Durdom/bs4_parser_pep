import requests_cache
import re
import logging
import argparse
from tqdm import tqdm
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from pathlib import Path

from constants import BASE_DIR, MAIN_DOC_URL, MAIN_URL_PEP, EXPECTED_STATUS
from outputs import control_output, file_output
from configs import configure_argument_parser, configure_logging
from utils import get_response, find_tag


# def configure_argument_parser(available_modes):
#     parser = argparse.ArgumentParser(description='Парсер документации Python')
#     parser.add_argument(
#         'mode',
#         choices=available_modes,
#         help='Режимы работы парсера'
#     )
#     parser.add_argument(
#         '-c',
#         '--clear-cache',
#         action='store_true',
#         help='Очистка кеша'
#     )
#     return parser


def whats_new(session):
    # Вместо константы WHATS_NEW_URL, используйте переменную whats_new_url.
    whats_new_url = urljoin(MAIN_DOC_URL, 'whatsnew/')


    # responce = session.get(whats_new_url)
    # responce.encoding = 'utf-8'
    responce = get_response(session, whats_new_url)
    if responce is None:
        return

    # print(responce.text)

    soup = BeautifulSoup(responce.text, features='lxml')

    main_div = find_tag(soup, 'section', attrs={'id': 'what-s-new-in-python'})
    div_with_url = find_tag(main_div, 'div', attrs={'class': 'toctree-wrapper'})
    sections = div_with_url.find_all('li', attrs={'class': 'toctree-l1'})
    # print(sections[0].prettify())
    results = [('Ссылка на статью', 'Заголовок', 'Редактор, автор')]
    for section in tqdm(sections):
        version_a_tag = section.find('a')
        href = version_a_tag['href']
        version_link = urljoin(whats_new_url, href)
        # Здесь начинается новый код!
        # response = session.get(version_link)  # Загрузите все страницы со статьями. Используйте кеширующую сессию.      
        # response.encoding = 'utf-8'  # Укажите кодировку utf-8.
        responce = get_response(session, version_link)
        if responce is None:
            continue
        soup = BeautifulSoup(responce.text, features='lxml')  # Сварите "супчик".
        h1 = find_tag(soup, 'h1')  # Найдите в "супе" тег h1.
        dl = find_tag(soup, 'dl')  # Найдите в "супе" тег dl.
        # print(version_link, h1.text, dl.text.replace('\n', ' ')) # Добавьте в вывод на печать текст из тегов h1 и dl. 
        results.append((version_link, h1.text, dl.text.replace('\n', ' ')))

    # for i in result:
    #     print(*i)

    return results


def latest_versions(session):

    # responce = session.get(MAIN_DOC_URL)
    # responce.encoding = 'utf-8'
    responce = get_response(session, MAIN_DOC_URL)
    if responce is None:
        return

    soup = BeautifulSoup(responce.text, features='lxml')

    sidebar = find_tag(soup, 'div', attrs={'class': 'sphinxsidebarwrapper'})
    ul_tags = sidebar.find_all('ul')

    # print(ul_tags)
    # Перебор в цикле всех найденных списков.
    for ul in ul_tags:
        # Проверка, есть ли искомый текст в содержимом тега.
        if 'All versions' in ul.text:
            # Если текст найден, ищутся все теги <a> в этом списке.
            a_tags = ul.find_all('a')
            # Остановка перебора списков.
            break
    # Если нужный список не нашёлся,
    # вызывается исключение и выполнение программы прерывается.
    else:
        raise Exception('Ничего не нашлось')
    # print(*a_tags, sep='\n')

    results = [('Ссылка на документацию', 'Версия', 'Статус')]
    pattern = r'Python (?P<version>\d\.\d+) \((?P<status>.*)\)'
    # Цикл для перебора тегов <a>, полученных ранее.
    for a_tag in a_tags:
        # Извлечение ссылки.
        link = a_tag['href']
        # Поиск паттерна в ссылке.
        text_match = re.search(pattern, a_tag.text)
        if text_match is not None:  
            # Если строка соответствует паттерну,
            # переменным присываивается содержимое групп, начиная с первой.
            version, status = text_match.groups()
        else:  
            # Если строка не соответствует паттерну,
            # первой переменной присваивается весь текст, второй — пустая строка.
            version, status = a_tag.text, ''  
        # Добавление полученных переменных в список в виде кортежа.
        results.append(
            (link, version, status)
        )

    # Печать результата.
    # for row in results:
    #     print(*row)
    return results


def download(session):
    # Вместо константы DOWNLOADS_URL, используйте переменную downloads_url.
    downloads_url = urljoin(MAIN_DOC_URL, 'download.html')
    
    download_dir = BASE_DIR / 'downloads'
    download_dir.mkdir(exist_ok=True)
    
    # responce = session.get(downloads_url)
    responce = get_response(session, downloads_url)
    if responce is None:
        return

    soup = BeautifulSoup(responce.text, features='lxml')
    main_tag = find_tag(soup, 'div', {'role': 'main'})
    table_tag = find_tag(main_tag, 'table', {'class': 'docutils'})
    pdf_a4_tag = find_tag(table_tag, 'a', {'href': re.compile(r'.+pdf-a4\.zip$')}) 
    archive_link = urljoin(downloads_url, pdf_a4_tag['href'])
    filename = archive_link.split('/')[-1]
    # print(pdf_a4_tag)
    # print(filename)
    archive_path = download_dir / filename

    file_d = session.get(archive_link)
    with open(archive_path, 'wb') as file:
        file.write(file_d.content)
    logging.info(f'Архив был скачан и сохранён: {archive_path}')

def pep(session):

    response = get_response(session, MAIN_URL_PEP)
    if response is None:
        return
    soup = BeautifulSoup(response.text, 'lxml')
    results = [('Status', 'Count')]
    results_dict = {}
    section_tag = find_tag(soup, 'section', attrs={'id': 'index-by-category'})
    table_tags = section_tag.find_all('tbody')
    for table_tag in tqdm(table_tags):
        tr_tags = table_tag.find_all('tr')
        for row_tag in tr_tags:
            status_tag = find_tag(row_tag, 'td')
            status_table = status_tag.text[1:]
            #print(status_table)
            link_tag = find_tag(
                row_tag, 'a', attrs={'href': re.compile(r'pep.+')}
            )
            href = link_tag['href']
            detail_pep_url = urljoin(MAIN_URL_PEP, href)
            pep_response = session.get(detail_pep_url)
            pep_response.encoding = 'utf-8'
            pep_soup = BeautifulSoup(pep_response.text, features='lxml')
            dl_tag = find_tag(pep_soup, 'dl')
            dt_tags = dl_tag.find_all('dt')
            for dt_tag in dt_tags:
                if 'Status' in dt_tag.text:
                    status_pep = dt_tag.find_next_sibling('dd').text
                    if status_pep in results_dict:
                        results_dict[status_pep] += 1
                    else:
                        results_dict[status_pep] = 1
                    if status_pep not in EXPECTED_STATUS[status_table]:
                        logging.info('Несовпадающие статусы:\n'
                                     f'{detail_pep_url}\n'
                                     f'Статус в карточке: {status_pep}\n'
                                     'Ожидаемые статусы:'
                                     f'{EXPECTED_STATUS[status_table]}'
                                    )
    for status, count in results_dict.items():
        results.append((status, count))
    results.append(('Total', sum(results_dict.values())))
    file_output(results, 'pep')


MODE_TO_FUNCTION = {
    'whats-new': whats_new,
    'latest-versions': latest_versions,
    'download': download,
    'pep': pep,
}


# def main():
#     arg_parser = configure_argument_parser(MODE_TO_FUNCTION.keys())
#     args = arg_parser.parse_args()

#     # Создание кеширующей сессии.
#     session = requests_cache.CachedSession()
#     # Если был передан ключ '--clear-cache', то args.clear_cache == True.
#     if args.clear_cache:
#         # Очистка кеша.
#         session.cache.clear()

#     parser_mode = args.mode
#     # С вызовом функции передаётся и сессия.
#     MODE_TO_FUNCTION[parser_mode](session)
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
    # Сохраняем результат вызова функции в переменную results. 
    results = MODE_TO_FUNCTION[parser_mode](session)
    
    # Если из функции вернулись какие-то результаты,
    if results is not None:
        # передаём их в функцию вывода вместе с аргументами командной строки.
        control_output(results, args)

    logging.info('Парсер завершил работу!')


if __name__ == '__main__':
    main()
