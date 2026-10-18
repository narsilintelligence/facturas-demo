# El kit del roadmap

Tres piezas para hacer con tu propio problema lo que en el vídeo hacemos con las facturas. Son las mismas que
usamos nosotros.

## 1. La hoja de tareas (`hoja-de-tareas.csv`)

Durante dos semanas, cada vez que hagas una tarea repetitiva en tu trabajo, prueba a hacerla con la IA y apúntala:
qué tarea era, cuánto tardas sin IA, qué encargo le hiciste, con qué modelo, cuánto tardaste con IA, si te sirvió y
qué falló. Ábrela con cualquier hoja de cálculo.

Al cabo de dos semanas, ordénala por tiempo ahorrado. La tarea que más se repite y más tiempo te quita es tu primer
proyecto. La nuestra fueron las facturas.

Un encargo bien hecho tiene cuatro partes: el **contexto** (quién eres y para qué es), el **objetivo** (qué quieres
exactamente), un **ejemplo** de cómo quieres el resultado y el **criterio** (cómo vas a saber que está bien).

## 2. La plantilla del banco de veinte casos (`plantilla-banco.csv`)

Un banco de pruebas son casos reales con la respuesta correcta apuntada **antes**, a mano. Con él decides con datos y
no por impresión.

- Elige veinte documentos de tu problema. Mete a propósito casos difíciles: en el nuestro, dos facturas escaneadas y
  dos con el IVA mal calculado (`banco.txt` y `verdad.csv` son nuestro banco ya relleno).
- Cambia `campo_1`…`campo_5` por los datos que quieres sacar (en las facturas: proveedor, fecha, base, IVA, total) y
  rellena cada fila con el valor correcto. Marca en `caso_dificil` los que lo son.
- Cada vez que cambies algo (el modelo, las instrucciones o una herramienta), vuelve a pasar los veinte y compara
  cuatro números: acierto por campo, invenciones (un dato que no está en el documento; dejarlo vacío no cuenta),
  tokens por caso y segundos por caso. `banco.py` hace exactamente eso con las facturas.
- Que el sistema diga que ha terminado no significa que haya terminado bien. Termina cuando el banco lo dice.

## 3. Las cuatro defensas

Para cualquier agente que lea contenido de fuera (una web, un correo, una factura) y pueda hacer algo:

1. **Permisos justos.** El agente solo puede hacer lo que necesita. Si solo tiene que avisar, no le des una
   herramienta que pague.
2. **Confirmación humana en lo que tiene consecuencias.** Lo que escribe, borra, paga o envía, lo confirma una
   persona. En `agente.py`, `marcar_pagada` pide un sí antes de escribir.
3. **Las contraseñas y las claves, nunca dentro de las instrucciones.** Ni en el código ni en un documento
   compartido ni en GitHub: en variables de entorno o en un gestor de secretos.
4. **Separar lo que lee de lo que decide.** El contenido de fuera es un dato, nunca una orden. Las instrucciones que
   aparezcan dentro de un documento se señalan como sospechosas, no se obedecen.

El ejercicio: esconde en uno de tus documentos de prueba una instrucción como la de nuestra factura F-0037 y mira qué
hace tu agente. Si la obedece, ya sabes qué tienes que arreglar. Es el primer riesgo de la lista de OWASP para
aplicaciones con modelos de lenguaje: la inyección de instrucciones.

## El plan de noventa días

Cuatro o cinco horas a la semana.

| Semana | Qué haces |
|---|---|
| 1 | Entiende lo justo de cómo funciona un modelo y empieza tu hoja de tareas. |
| 2 | Usa dos o tres modelos cada día e instala uno local. |
| 3-4 | Python básico, la terminal y Git. Meta: un programa que cuente tus documentos, sin IA dentro. |
| 5-6 | Tu primer proyecto con la API, terminado con tus datos y con su hoja de costes. |
| 7-8 | Que responda a tus preguntas con cita, y diez preguntas cuya respuesta conoces para probarlo. |
| 9 | Conviértelo en un agente con dos herramientas y confirmación. |
| 10 | Su banco de veinte casos y la comparación entre un modelo grande y uno local. |
| 11 | Intenta engañarlo y ciérrale los agujeros. |
| 12 | Documéntalo: qué resuelve, cómo lo mediste y cuánto ahorra. |

Al final no serás un experto. Tendrás algo mejor: un agente pequeño, tuyo, que resuelve un problema real, medido y
protegido.
