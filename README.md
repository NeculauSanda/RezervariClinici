Fisierul de teste se ruleaza astfel:

python3 test.py

!!! componenta pe care am ales-o sa o replic este appointment-service de la modul 1 avansat !!!

1. Prima data se initializeaza Dockerul si se fac imaginile, o sa dureze ceva
2. Se ruleaza aplicatia, pana sunt up toate si baza de date, dureaza putin
3. Incepe rularea testelor, dupa ce se obtin token-urile pentru utilizatorii deja pusi de mine
4. Cate teste au trecut sau au picat
5. Inchiderea stack-ului,iesirea din swarm, stergerea imaginilor si a volumelor trebuie facute manual, (am lasat asa ca se se confirme si verificarea mailurilor si a pdf-urilor trimise pe mailHog http://localhost:8025/# + verificarea serviciului appointments sa se vada ca functioneaza duplicarea si coada (testare: docker service logs -f medical_app_appointment-worker docker service logs -f medical_app_appointment-service))
