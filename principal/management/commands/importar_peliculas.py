# Django Imports
from django.core.management.base import BaseCommand

# Python Standard Library Imports
import time
from decimal import Decimal, InvalidOperation

# Third-party Imports
from selenium import webdriver
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup

# Local App Imports
from principal.models import Pelicula, Categoria

class Command(BaseCommand):
    help = 'Ejecuta un scraper para buscar películas en IMDb por año y las guarda en la base de datos.'

    def handle(self, *args, **options):
        # --- CONFIGURACIÓN INICIAL ---
        año_actual = 2003 # O el año que desees para empezar
        todos_los_links = []
        
        # --- CONFIGURACIÓN DE SELENIUM ---
        ruta_al_driver = r"C:\edgedriver\msedgedriver.exe"
        servicio_edge = EdgeService(executable_path=ruta_al_driver)
        opciones_edge = webdriver.EdgeOptions()
        opciones_edge.add_experimental_option('excludeSwitches', ['enable-logging'])
        opciones_edge.add_argument("--headless") # Ejecuta el navegador en segundo plano (más rápido)
        opciones_edge.add_argument("--inprivate")
        opciones_edge.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        
        self.stdout.write(self.style.NOTICE("Iniciando driver de Selenium..."))
        driver = webdriver.Edge(service=servicio_edge, options=opciones_edge)

        try:
            # --- FASE 1: OBTENER TODOS LOS LINKS DE PELÍCULAS ---
            self.stdout.write(self.style.NOTICE("--- FASE 1: Recopilando links de películas ---"))
            año = año_actual
            while año >= 1960:
                url = f"https://www.imdb.com/search/title/?title_type=feature&release_date={año}-01-01,{año}-12-31&user_rating=5,10&num_votes=50000,&sort=user_rating,desc&ref_=adv_prv"
                driver.get(url)
                
                try:
                    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "li.ipc-metadata-list-summary-item")))
                    self.stdout.write(f"Página del año {año} cargada. Obteniendo resultados...")

                    # Cargar todos los resultados haciendo clic en "Ver más"
                    while True:
                        try:
                            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                            time.sleep(1)
                            boton = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.ipc-see-more__button")))
                            driver.execute_script("arguments[0].click();", boton)
                            self.stdout.write(self.style.SUCCESS("  -> Botón 'Ver más' presionado..."))
                            time.sleep(2)
                        except (TimeoutException, NoSuchElementException):
                            self.stdout.write(f"  -> Se cargaron todas las películas del año {año}.")
                            break

                    # Extraer los links de la página completamente cargada
                    html = driver.page_source
                    sopa = BeautifulSoup(html, 'html.parser')
                    lista_pelis = sopa.find_all('li', class_='ipc-metadata-list-summary-item')
                    
                    for pelicula_html in lista_pelis:
                        link_tag = pelicula_html.find('a', class_='ipc-title-link-wrapper')
                        if link_tag and 'href' in link_tag.attrs:
                            link_relativo = link_tag['href']
                            link_completo = f"https://www.imdb.com{link_relativo.split('?')[0]}" # Limpiamos el link de parámetros
                            if link_completo not in todos_los_links:
                                todos_los_links.append(link_completo)

                except TimeoutException:
                    self.stdout.write(self.style.WARNING(f"No se encontraron películas o la página tardó mucho en cargar para el año {año}."))
                
                año -= 1

            self.stdout.write(self.style.SUCCESS(f"\n✅ FASE 1 COMPLETADA. Se encontraron {len(todos_los_links)} links únicos.\n"))

            # --- FASE 2: EXTRAER DETALLES Y GUARDAR EN LA BASE DE DATOS ---
            self.stdout.write(self.style.NOTICE("--- FASE 2: Extrayendo detalles y guardando en la BBDD ---"))
            for link in todos_los_links:

                # Verificamos si la película ya existe en la BBDD para no procesarla de nuevo
                if Pelicula.objects.filter(link_imdb=link).exists():
                    self.stdout.write(self.style.WARNING(f"Película ya existe en la BBDD. Saltando: {link}"))
                    continue

                driver.get(link)
                self.stdout.write(f"\nVisitando: {link}")
                
                try:
                    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='hero__pageTitle']")))
                    html_detalle = driver.page_source
                    sopa_detalle = BeautifulSoup(html_detalle, 'html.parser')
                    
                    # --- EXTRACCIÓN DE DATOS ---
                    # (Se usan bloques try-except para cada dato por si alguno falta en la página)
                    try:
                        titulo = sopa_detalle.find('span', {'data-testid': 'hero__primary-text'}).text.strip()
                    except:
                        titulo = "No encontrado"
                    
                    try:
                        titulo_original_div = sopa_detalle.find('h1', {'data-testid': 'hero__pageTitle'}).find_next_sibling('div')
                        titulo_original = titulo_original_div.text.replace('Título original: ', '').strip()
                    except:
                        titulo_original = titulo

                    try:
                        poster_src = sopa_detalle.find('div', {'data-testid': 'hero-media__poster'}).find('img')['src']
                    except:
                        poster_src = None

                    try:
                        metadata_list = sopa_detalle.select_one("[data-testid='hero__pageTitle'] ~ ul")
                        metadata_items = metadata_list.find_all('li')
                        año_str = metadata_items[0].text.strip()
                        duracion = metadata_items[-1].text.strip()
                    except:
                        año_str = "0"
                        duracion = "No encontrada"

                    try:
                        sinopsis = sopa_detalle.find('span', {'data-testid': 'plot-xs_to_m'}).text.strip()
                    except:
                        sinopsis = "No encontrada"

                    try:
                        director = sopa_detalle.select_one('a[href*="/name/"]').text.strip()
                    except:
                        director = "No encontrado"
                    
                    try:
                        calificacion_str = sopa_detalle.find('div', {'data-testid': 'hero-rating-bar__aggregate-rating__score'}).find('span').text.strip()
                    except:
                        calificacion_str = "0.0"

                    try:
                        categorias_div = sopa_detalle.find('div', {'data-testid': 'interests'})
                        categorias_tags = categorias_div.find_all('span', class_='ipc-chip__text')
                        categorias_nombres = [tag.text.strip() for tag in categorias_tags]
                    except:
                        categorias_nombres = []

                    # --- CONVERSIÓN Y LIMPIEZA DE DATOS ---
                    try:
                        estreno_final = int(año_str)
                    except (ValueError, TypeError):
                        estreno_final = None

                    try:
                        rating_final = Decimal(calificacion_str.replace(',', '.'))
                    except (InvalidOperation, TypeError):
                        rating_final = None

                    # --- GUARDADO EN LA BASE DE DATOS ---
                    # 1. Gestionar las categorías
                    categorias_a_asignar = []
                    for nombre_cat in categorias_nombres:
                        categoria_obj, created = Categoria.objects.get_or_create(nombre=nombre_cat)
                        categorias_a_asignar.append(categoria_obj)
                    
                    # 2. Crear el objeto Pelicula y guardarlo
                    pelicula_obj = Pelicula.objects.create(
                        titulo = titulo,
                        titulo_original = titulo_original,
                        link_imdb = link,
                        estreno = estreno_final,
                        duracion = duracion,
                        sinopsis = sinopsis,
                        director = director,
                        rating = rating_final,
                        poster_url = poster_src,
                    )

                    # 3. Asignar las categorías a la película (relación ManyToMany)
                    if categorias_a_asignar:
                        pelicula_obj.categorias.set(categorias_a_asignar)

                    self.stdout.write(self.style.SUCCESS(f"  -> ✅ Película '{titulo}' guardada correctamente en la BBDD."))
                    
                    time.sleep(1) # Pequeña pausa para no sobrecargar el servidor

                except TimeoutException:
                    self.stdout.write(self.style.ERROR(f"  -> ❌ Error: La página {link} tardó demasiado en cargar o no tiene el formato esperado."))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  -> ❌ Error inesperado al procesar {link}: {e}"))

        finally:
            driver.quit()
            self.stdout.write(self.style.SUCCESS("\n✅ Scraping completo y driver cerrado."))