DeLorean
========

Geração de bases ISIS (formato ID), com base em dados
obtidos via API do Journal Manager (gerenciador de catálogo
do SciELO periódicos).


.. image:: https://secure.travis-ci.org/scieloorg/delorean.png?branch=master
`See Build details <http://travis-ci.org/#!/scieloorg/delorean>`_


Sobre o formato ID:
-------------------
http://bvsmodelo.bvsalud.org/download/cisis/CISIS-ManualReferencia-pt-5.2.pdf
(página 139)

    • !ID nnnnnn Marca de começo de registro com mfn=nnnnnn
    • !vnnn  Marca de começo de uma ocorrência do campo com tag nnn.


O arquivo terá a forma::

    !ID nnnnnn
    !vXXX!...conteúdo da tag XXX.............
    !vYYY!...conteúdo da tag YYY.............
    ...
    !ID nnnnnj
    !vXXQ!...conteúdo da tag XXQ.............
    !vYYQ!...conteúdo da tag YYQ.............
    ...
