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


FAQ:
    * A codificação do arquivo ID deve ser ASCII, conforme consta na
      documentação da Bireme?

      **R:** Não, é possível que seja CP-1252.

    * Existe uma maneira de delegarmos a criação do mfn para o CISIS?

      **R:** Sim. Pode-se utilizar a sintaxe ``!ID 0`` para todos os registros
      e no utilitário id2i utilizar a opção ``app``::

        id2i arq.id create/app=i
