Fisierul de teste se ruleaza astfel:

python3 test.py

!!! La mine user-service este replicat doar pentru testare ca sa vad daca merge, componenta pe care am ales-o sa o 
replic este appointment-service de la modul 1 avansat !!!

1. Prima data se initializeaza Dockerul si se fac imaginile, o sa dureze ceva
2. Se ruleaza aplicatia, pana sunt up toate si baza de date, dureaza putin
3. Incepe rularea testelor, dupa ce se obtin token-urile pentru utilizatorii deja pusi de mine
4. Cate teste au trecut sau au picat
5. Inchiderea stack-ului,iesirea din swarm, stergerea imaginilor si a volumelor, doar a aplicatiei mele
