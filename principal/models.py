# principal/models.py
from django.db import models

class Categoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True, help_text="Nombre del género o categoría")

    def __str__(self):
        return self.nombre
    
    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"

class Pelicula(models.Model):
    titulo = models.CharField(max_length=255, help_text="Título principal de la película")
    titulo_original = models.CharField(max_length=255, null=True, blank=True, help_text="Título en su idioma original")
    link_imdb = models.URLField(max_length=500, unique=True, help_text="Enlace único de IMDb para evitar duplicados")
    
    estreno = models.PositiveIntegerField(null=True, blank=True, help_text="Año de lanzamiento")
    duracion = models.CharField(max_length=50, null=True, blank=True, help_text="Duración en formato texto (ej: 2h 22m)")
    sinopsis = models.TextField(null=True, blank=True, help_text="Resumen o trama de la película")
    
    director = models.CharField(max_length=200, null=True, blank=True, help_text="Nombre del director")
    rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True, help_text="Puntuación con un decimal (ej: 8.7)")
    poster_url = models.URLField(max_length=500, null=True, blank=True, help_text="URL de la imagen del póster")
    
    categorias = models.ManyToManyField(Categoria, blank=True, related_name="peliculas")

    def __str__(self):
        return f"{self.titulo} ({self.estreno})"

    class Meta:
        ordering = ['-estreno', 'titulo']
        verbose_name = "Película"
        verbose_name_plural = "Películas"