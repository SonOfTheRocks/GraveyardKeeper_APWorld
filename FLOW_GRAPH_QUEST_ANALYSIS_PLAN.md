# Übergabeplan: Questbedingungen aus FlowGraphExports untersuchen

Stand: 25.09.2026. Dieses Dokument beschreibt die fachlich konkretisierte und inzwischen umgesetzte
Zielausgabe. Die frühere ausführliche Pfad-/Belegausgabe wurde durch die nachfolgend beschriebene kompakte,
belohnungsbezogene Zusammenfassung ersetzt; technische Details bleiben optional über `--details` verfügbar.

## 1. Auftrag und verbindliche Abgrenzung

Ein Python-Werkzeug soll die exportierten Graveyard-Keeper-FlowGraphs analysieren und die Bedingungen für ItemDrops und Einflussgewinne bei NPCs verständlich auflisten. Die Ergebnisse dienen dem Benutzer zur einmaligen, manuellen Übertragung in die APWorld-Questdaten.

**Das gewünschte Endprodukt sind kompakte, unmittelbar lesbare Markdown-Einträge pro konkreter
Belohnungsoption beziehungsweise Belohnungspfad.** Die Einträge sollen nicht primär den Graphen erklären,
sondern genau die für die manuelle Questpflege benötigten Inhalte gruppieren: Datei, Belohnung,
MultiAnswer-Phrase, Gesprächszeilen, Task-State-Änderungen, Phrase-Blacklist und zusätzliche
Anzeige-/Auswahlbedingungen. Eine JSON-Ausgabe ist nicht erforderlich. Insbesondere soll das Werkzeug
keine exakten produktiven Questdateien generieren oder bestehende Questdaten überschreiben. Namen,
Gruppierung und endgültige APWorld-Modellierung übernimmt der Benutzer mit seinem Spielkontext.

Die bisherige Visualisierung allein reicht nicht: Gesucht sind die Bedingungen, unter denen eine konkrete Belohnung erreichbar ist, einschließlich der Bedingungen einer gewählten Gesprächsoption und vorgelagerter Ablaufzweige. Weitere Ziel-Node-Typen sollen später mit überschaubarem Aufwand ergänzt werden können.

Die ausführliche Node-/Port-Kette bleibt als optionale Diagnose beziehungsweise maschinennahe Begründung
erhalten, darf aber die Hauptausgabe nicht dominieren. Ein Eintrag ohne die oben genannten fachlichen
Gruppen gilt nicht als brauchbares Ergebnis, auch wenn der Kontrollflusspfad technisch korrekt gefunden wurde.

### 1.1 Verbindliches Zielbild am Referenzfall

Für `npc_astrologer.json` ist die relevante Struktur von `@astrologer_charm_no` inzwischen belegt:

```text
Flow_MultiAnswer 44, answers[7] = @astrologer_charm_no
44.out_7 -> CustomFunctionCall 292
292._sourceOutputUID = e16b49b8-962f-4fff-9bd6-c933d87c2403
CustomFunctionEvent 748._UID = e16b49b8-962f-4fff-9bd6-c933d87c2403
CustomFunctionEvent 748.identifier = @astrologer_charm_no
748 -> Flow_AddPhraseToBlacklist 752
    -> Flow_Talk 754/756/758
    -> Flow_SetTaskState 760
    -> Flow_Talk 762/764/766/768
    -> Flow_SetTaskState 770
    -> Flow_Talk 772
    -> Flow_AddRelation 774
    -> Return 776
```

Die fachliche Hauptausgabe soll mindestens folgende Form erreichen:

```markdown
file: npc_astrologer.json

add_relation: 10.0

multi_answer: @astrologer_charm_no

conversations:

- astrologer_charm_no_8
- astrologer_charm_no_7
- astrologer_charm_no_6
- astrologer_charm_no_5
- astrologer_charm_no_4
- astrologer_charm_no_3
- astrologer_charm_no_2
- astrologer_charm_no_1

task_states:

- astrologer_daghter: Complete
- astrologer_help: Visible

phrases_to_blacklist:

- astrologer_charm_no
```

Die Gesprächsliste wird für diese rückwärts von der Belohnung ermittelte Zusammenfassung
belohnungsnah zuerst ausgegeben, damit sie dem bestätigten manuellen Referenzergebnis entspricht.
Andere Listen müssen deterministisch sein; wenn Reihenfolge spielsemantisch relevant ist, muss zusätzlich
die tatsächliche Ausführungsreihenfolge intern erhalten und in einer Diagnoseansicht abrufbar bleiben.

Der dekorierte Input `#7` von MultiAnswer 44 ist lokal `null` und besitzt keine angeschlossene AnswerData.
Damit sind für diese Option keine `lock`-/`price`-/`reward`-Werte am Input belegt. Die Phrase
`@astrologer_charm_no` wird jedoch in `npc_actress.json` durch `Flow_UnlockPhrase` 371 freigeschaltet.
Dies ist eine konkrete graphübergreifende Questvoraussetzung. Nach Benutzerbestätigung können alle
nichtleeren Phrases eine Questvoraussetzung darstellen, nicht nur Phrases mit führendem `@`. Daher wird
jede Phrase als `required_quests` geführt und mit allen gefundenen `Flow_UnlockPhrase`-Quellen verknüpft;
ein vorhandenes führendes `@` wird im Questschlüssel entfernt.

Nicht Bestandteil dieses Auftrags:

- Änderungen an APWorld-Generierung, Regeln, Item-/Location-IDs oder Clientverhalten;
- automatische vollständige Rekonstruktion aller Spielzustände und sämtlicher Questketten;
- neue Website, neue Graphvisualisierung oder ein allgemeiner FlowCanvas-Interpreter;
- Installation externer Graph-Libraries ohne konkreten Bedarf;
- endgültige Benennung oder automatische Zusammenfassung von Belohnungen zu APWorld-Quests.

## 2. Repositories, Quellen und Arbeitsregeln

APWorld-Root:

`C:\Users\Kai\PycharmProjects\Archipelago_GraveyardKeeper`

Client-Root:

`C:\Users\Kai\RiderProjects\GraveyardKeepelago`

Die Dump-Verzeichnisse liegen im **Unterprojekt** des Clients, nicht direkt im Repository-Root:

- `GraveyardKeepelago/Dumps/FlowGraphExports/*.json`
- `GraveyardKeepelago/Dumps/make_htmls_old.py`
- `GraveyardKeepelago/Dumps/index.html`
- `GraveyardKeepelago/Dumps/FlowGraphExports_HTML/`
- `GraveyardKeepelago/Dumps/Decompiled/`

Relevante APWorld-Dateien:

- `worlds/graveyard_keeper/data/quest_events.json`: tatsächlich vorgefundenes Zielformat; vom Benutzer auch als quest_data bezeichnet;
- `worlds/graveyard_keeper/models.py`: `QuestEventData`, `HappinessData`;
- `worlds/graveyard_keeper/logic/custom_rules.py`: insbesondere `CanComplete`, `HasHappiness`;
- `worlds/graveyard_keeper/data/items/quest/` und weitere Itemdaten für Zuordnungsvorschläge;
- `worlds/graveyard_keeper/test/data_integrity/test_quest_events.py`.

Vor Umsetzung die AGENTS.md beider Repositories und gegebenenfalls zusätzliche Regeln im Zielverzeichnis lesen. Unrelated Änderungen erhalten. Keine IDs, Spielsemantik oder NPC-Zuordnung erraten.

Vor Python-Skripten und Tests gemäß APWorld-Regeln Setup prüfen und vom Root `python ModuleUpdate.py` ausführen. Unterstütztes Python: mindestens 3.11.9, unter 3.14, kein Windows-Store-Python. Das Setup und die Tests wurden mit der Repository-`.venv` ausgeführt; die konkreten Resultate werden bei der Übergabe berichtet.

`git status --short` wurde in der Sandbox wegen unterschiedlicher Repository-Eigentümer blockiert. Bei Bedarf den eng begrenzten Aufruf `git -c safe.directory=C:/Users/Kai/PycharmProjects/Archipelago_GraveyardKeeper status --short` verwenden; keine globale Git-Konfiguration ändern.

## 3. Bereits belegte Struktur und Referenzfälle

Untersucht wurde insbesondere `npc_astrologer.json`. Die folgenden Angaben sind Dump-Befunde; sie sind keine vollständige Bestätigung der Laufzeitsemantik.

### Graphstruktur

- Top-Level enthält unter anderem `nodes`, `connections`, `localBlackboard`.
- Nodes besitzen `$id`, `$type`, häufig `_inputPortValues`; teilweise `_UID` und Wrapper-Daten.
- Verbindungen referenzieren Nodes über `_sourceNode.$ref` und `_targetNode.$ref` und besitzen Quell-/Zielportnamen.
- Einfache Werte sind oft als `{"$content": ..., "$type": ...}` gespeichert.
- Generische `SimplexNodeWrapper` enthalten den eigentlichen Typ im `$type`-String, beispielsweise `Flow_Answer` oder `Flow_SmartRes`.
- Es existieren exakt doppelte Verbindungen. Diese dürfen weder zusätzliche Pfade noch doppelte Belohnungen erzeugen.
- Kontrollflussverbindungen und typisierte Datenverbindungen sind getrennt zu behandeln. Im untersuchten Dump existieren beispielsweise `BinderConnection` und `BinderConnection<AnswerData>` beziehungsweise `<SmartRes>`.

### MultiAnswer-Mapping

Bei Node 44 stehen die Phrase-IDs in `answers`. Die dekorierten Eingänge heißen beispielsweise `<color=#A08030>#3</color>`. Der zugehörige Ausgang ist `out_3`.

Belegtes Beispiel:

```text
Flow_SmartRes 473: Item, acid, 1
  --Value--> Flow_Answer 476.price
Flow_SmartRes 594: GameRes, _rel, 10
  --Value--> Flow_Answer 476.reward
Flow_Answer 476.Value
  --> Flow_MultiAnswer 44.<color=#A08030>#3</color>
answers[3] = @astrologer_acid
zugehöriger Kontrollflussausgang = out_3
```

Das belegt Optionskosten und eine kodierte Relationsbelohnung. Es belegt für sich allein noch nicht die vollständige Erreichbarkeit dieser Option, den Empfänger oder den genauen Zeitpunkt der Belohnung.

Weitere Befunde aus demselben Dump:

- `Flow_DropItem` 163: `Res_id = quest_key_astrologer`, `Amount = 1`;
- `Flow_AddRelation` 742 und 774: jeweils `Value = 10`, gespeicherte `npc_id = null`;
- `Flow_ParamFlag` besitzt unter anderem die Kontrollflussausgänge `>= 1` und `== 0`;
- `Flow_SetTaskState` enthält `Task`, `State`, `NPC id` und Story-Felder; beobachtet wurden `Visible` und `Complete`;
- leere gespeicherte `SmartRes`-/`AnswerData`-Werte können durch angeschlossene Datenlieferanten ergänzt beziehungsweise ersetzt werden.

Das alte Visualisierungsskript kennt bereits die Zuordnung `out_i -> answers[i]`, UID-basierte Funktionsverweise und eine vereinfachte Eventdarstellung. Es ist eine Strukturhilfe, keine verbindliche Ausführungssemantik. Seine pauschale Entfernung von Steuerzeichen aus JSON nicht ungeprüft übernehmen.

Im Client-Verzeichnis `GraveyardKeepelago/Dumps/Decompiled` ist lokal nur
`Assembly-CSharp-firstpass` vorhanden. Der vollständige dekompilierte Haupt-Quellbaum wurde inzwischen unter
`C:\Users\Kai\RiderProjects\Graveyard Keeper Asset Export\Scripts\Assembly-CSharp` gefunden. Dort sind
insbesondere `GameSave.cs`, `MultiAnswerGUI.cs`, `TechDefinition.cs` und die FlowCanvas-Node-Klassen belegt.
Die HTML-Indexdatei enthält sehr große eingebettete Datenzeilen: bei Suche keine vollständigen Trefferzeilen
ausgeben.

### Belegte Phrase-Sichtbarkeit und Technologie-Daten

- `GameSave.unlocked_phrases` wird als leere Liste initialisiert. `CreateNewSave()` und
  `QuestSystem.InitQuestSystem()` tragen keine anfänglichen Phrases ein.
- `MultiAnswerGUI.ShowAnswers()` prüft `unlocked_phrases` nur für Antwort-IDs mit führendem `@`.
  Eine Phrase ohne `@` ist beim neuen Spiel sichtbar, solange sie nicht in `black_list_of_phrases` steht.
  Sie bleibt für die fachliche Analyse dennoch ein `required_quests`-Eintrag.
- `Flow_UnlockPhrase` fügt eine Phrase zu `unlocked_phrases` hinzu.
- `Flow_AddPhraseToBlacklist(remove=true)` entfernt eine Phrase aus der Blacklist und ist damit ebenfalls
  eine belegte Sichtbarkeitsquelle. Diese Nodes müssen wie Unlock-Quellen gerichtete Graphkanten erzeugen.
- `GameSave.UnlockTech()` kopiert `TechDefinition.phrases` nach `unlocked_phrases` und startet danach den
  optionalen `flowscript` der Technologie.
- Im vorliegenden `worlds/graveyard_keeper/dumps/raw/techs_data.json` sind jedoch bei allen 187
  Technologien die `phrases`-Listen leer. Die 19 Technologie-Flows enthalten im aktuellen Export ebenfalls
  keine `Flow_UnlockPhrase`-Nodes. Daher darf der Analyzer aus diesen Daten derzeit keine direkten
  Technologie→Phrase-Kanten erfinden. Betroffene `@`-Phrases ohne andere Quelle bleiben als konkrete
  Uncertainty sichtbar.
- `Flow_DropItem.RegisterPorts()` setzt `Amount` auf den Laufzeitdefault `1`. Fehlt der unveränderte Port
  im Export und liefert auch kein angeschlossenes Item eine Menge, ist die korrekte Drop-Menge daher `1`
  und nicht unbekannt.

## 4. Ergebnisformat: kompakte belohnungsbezogene Markdown-Zusammenfassung

Empfehlung: eine Übersicht `README.md` und eine Datei pro Graph oder sinnvoller NPC-Gruppe. Dateigrenzen und NPC-Identität nicht gleichsetzen; ein Graph kann mehrere NPCs betreffen. Die erste Version darf pro Graph berichten und einen NPC-Index anbieten.

Zusätzlich wird `QUEST_GRAPH.html` als interaktive Hauptansicht erzeugt. Jeder Belohnungsfund sowie zum
Verbinden notwendige Phrase-Funde ist ein Knoten. Gerichtete Kanten laufen von Funden mit
`Flow_UnlockPhrase` zu Funden, welche dieselbe Phrase benötigen oder blacklisten. Hover zeigt eine kompakte
Zusammenfassung; Auswahl per Klick oder Suchergebnis öffnet die vollständige Detailansicht. Suche und
Graphfilter orientieren sich an der vorhandenen Dump-`index.html`.

Ein Belohnungsfund wird niemals allein deshalb aus dem Endgraphen entfernt, weil sein eingehender
Ausführungspfad noch nicht aufgelöst ist. Solche Funde bleiben als Reward-Knoten sichtbar und werden in
Tooltip, Detailansicht und `uncertainties` ausdrücklich als „Ausführungseinstieg nicht aufgelöst“ markiert.

Die Hauptansicht pro Fund ist kein allgemeiner Erklärbericht. Sie besteht aus kurzen, nur bei Bedarf
vorhandenen Feldern:

- `file`;
- eine gemeinsame `rewards`-Liste mit `item_drop`- und `relation`-Einträgen einschließlich Menge;
- soweit belegbar den NPC eines Relationsgewinns beziehungsweise einer Happiness-Anforderung und die
  Herkunft dieser Zuordnung;
- `multi_answer` und optional `multi_answer_index`;
- `conversations` aus den `Text`-Werten der relevanten `Flow_Talk`-Nodes;
- `task_states` aus `Flow_SetTaskState`;
- `phrases_to_blacklist` aus `Flow_AddPhraseToBlacklist` mit `remove = false`;
- `phrases_removed_from_blacklist` bei `remove = true`;
- `phrase_requirements` einschließlich gefundener `Flow_UnlockPhrase`-Quellen;
- `locks`, `costs` und `answer_rewards` aus der AnswerData des exakt zugehörigen MultiAnswer-Inputs;
- `other_requirements` für belegte Flags, Relationsschwellen, Items, DLC oder externe Events;
- `uncertainties` nur für konkret diesen Fund betreffende offene Semantik.

Leere Gruppen werden standardmäßig weggelassen. „Unbekannt“ und „leer“ bleiben verschieden: Ein Feld wird
nur dann als leer behandelt, wenn der relevante Pfadausschnitt vollständig ausgewertet wurde. Technische
Node-IDs, Ports und lange Belegketten gehören in eine optionale `details`-Sektion oder separate Diagnoseausgabe.

Pro Belohnungsfund eine stabile interne Referenz aus Graph, Belohnungs-Node und gegebenenfalls Optionsindex
verwenden. Gleiche Items an unterschiedlichen Stellen separat erhalten. Die stabile Referenz muss nicht als
prominente Überschrift erscheinen. Keine erfundenen produktiven Event- oder Location-IDs verwenden.

Einträge sollen folgende Informationen enthalten:

1. Belohnungsart, Item-ID und Menge beziehungsweise NPC und Einflussänderung;
2. Quelldatei, Node-ID, gegebenenfalls Phrase und MultiAnswer-Index;
3. die zur gewählten Option gehörenden Gesprächszeilen;
4. Task-State- und Phrase-Blacklist-Änderungen zwischen Option und Belohnung;
5. Anzeige-/Auswahlbedingungen der Option, insbesondere Phrase-Freischaltung und AnswerData-`lock`;
6. Kosten/Verbrauch getrennt von Besitz-/Zugangsbedingungen;
7. weitere relevante Zustandsänderungen auf dem Pfad;
8. Vorschläge für vorhandene APWorld-Keys mit Herkunft und Unsicherheiten;
9. optional eine kurze überprüfbare Node-/Port-Kette;
10. Analysezustand und offene Fragen.

Das frühere ausführliche Beispiel ist nur noch eine Diagnoseansicht. Die primäre Gestaltung richtet sich
nach Abschnitt 1.1. Falls zusätzliche Anforderungen belegt sind, werden sie kompakt ergänzt, beispielsweise:

```markdown
file: npc_astrologer.json
add_relation: 10.0
multi_answer: @astrologer_acid
costs:
- item: acid
  amount: 1
phrase_requirements:
- phrase: astrologer_acid
  source: noch zu ermitteln
uncertainties:
- Empfänger des impliziten Relationsgewinns noch nicht belegt
```

Unbekannt ist nicht gleich leer: Ungeklärte Voraussetzungen ausdrücklich ausschreiben. Vollständig analysierte leere Anforderungen dürfen als „keine innerhalb des angegebenen Einstiegs nachgewiesen“ erscheinen. Die Abhängigkeit von extern ausgelösten Events muss trotzdem sichtbar bleiben.

Für mehrere Pfade jeweils eine eigene UND-Liste unter „Alternative A/B/...“ darstellen. Eine Vermischung aller Bedingungen zu einer einzigen Liste wäre logisch falsch.

## 5. Umsetzungsschritte

### Schritt A: Bestandsaufnahme und Semantikprüfung

Alle JSON-Dateien inventarisieren: Node-Typen, Verbindungstypen, Zieltypen, Referenzen, nicht lesbare Dateien. Die spätere Analyse muss auch Nicht-NPC-Graphen berücksichtigen, da diese Voraussetzungen oder Belohnungen enthalten können.

Anhand verfügbarer Spielquellen oder gezielt untersuchter Assemblies klären:

- Semantik und Defaultwerte von `Flow_Answer`, `AnswerData`, `SmartRes`;
- Unterschiede zwischen `lock`, `price`, `reward` sowie Sichtbarkeit und Auswählbarkeit;
- Phrase-Freischaltungen und Blacklist für Phrases mit und ohne `@`-Präfix;
- Vorrang angeschlossener Werte, Bedeutung von `null` und nicht serialisierten Defaults;
- NPC-/WGO-Kontext bei leeren Eingaben und `GameRes _rel`;
- Zeitpunkt von Kostenabbuchung und Belohnung relativ zum ausgewählten Ausgang;
- `Flow_SetTaskState`, Relationsvergleiche, Funktionsaufrufe und Eventauslösung.

Alle nichtleeren MultiAnswer-Phrases als mögliche Questvoraussetzung behandeln. Das `@`-Präfix ist dafür
keine Voraussetzung und wird lediglich bei der Normalisierung des Questschlüssels entfernt. Fehlende
`Flow_UnlockPhrase`-Quellen als konkrete offene Evidenz dokumentieren. Wenn erforderliche Spielquellen fehlen,
gezielt danach fragen.

### Schritt B: Normalisiertes Graphmodell und Parser

Kleine Dataclasses und Standardbibliothek genügen zunächst. Vorgeschlagene Bestandteile: Graph, Node, Edge, SourceRef, symbolischer Wert, Bedingung und Effekt.

- Node-Identität immer durch Graph plus lokale ID bestimmen.
- Typnamen inklusive Wrapper sauber normalisieren; Originaltyp erhalten.
- Eingehende Datenkanten pro Zielport, ausgehende Flow-Kanten pro Quellport indizieren.
- Rohwerte, Referenzen, Blackboard-Bezüge und Verbindungen auflösen; nicht auf `$content` allein reduzieren.
- Identische Verbindungen deduplizieren, unterschiedliche Mehrfachbelegungen diagnostizieren.
- Original-Portnamen als Beleg erhalten; dekorierte MultiAnswer-Ports zusätzlich normalisieren.
- Ungültige JSON-Daten mit Dateipfad melden. Falls reale Dumps nicht standardkonforme Steuerzeichen enthalten, nur gezielte dokumentierte Kompatibilitätsbehandlung einsetzen und testen; keine stille Datenbereinigung.

### Schritt C: Datenfluss auswerten und Gesprächsoptionen normalisieren

Eine Funktion zur symbolischen Auflösung eines Eingabeports einführen. Sie berücksichtigt gemäß bestätigter Semantik angeschlossene Ausgänge, lokale Werte und Defaults. Dynamische oder zyklische Datenabhängigkeiten liefern einen ausdrücklich ungelösten Ausdruck mit Herkunft.

Für jede MultiAnswer-Option den numerischen Index aus `#i` lesen, mit `answers[i]` und `out_i` verbinden und das zugehörige AnswerData auflösen. Nicht lexikographisch sortieren und nicht anhand der Reihenfolge der Verbindungen zuordnen. Inline-AnswerData und angeschlossene Flow_Answer-Nodes unterstützen. Fehlende Daten und nicht belegte Ausgänge getrennt behandeln.

`Flow_Answer` ist in den untersuchten Beispielen ein Wertelieferant. Seine Belohnung wird deshalb am nachgewiesenen Auswahl-/Ausführungsereignis der Option verortet, nicht schon beim bloßen Vorhandensein des Daten-Nodes. Derselbe Answer-Node kann mehrere Verwendungen haben; Auswahlkontext nicht verlieren.

Zusätzlich muss jede Option eine eigenständige fachliche Identität erhalten, die aus
`MultiAnswer + Index + Phrase + out_i` besteht. Von `out_i` aus sind lokale Funktionsaufrufe über
`CustomFunctionCall._sourceOutputUID -> CustomFunctionEvent._UID` transparent zu verfolgen. Call und Event
sind eine strukturelle Aufrufgrenze, keine eigene Questbedingung. `identifier`, Parameter, Return-Node und
Fortsetzung bleiben als Kontext erhalten.

Für die Optionsanzeige sind zwei getrennte Anforderungsquellen zu erfassen:

1. explizite AnswerData am dekorierten Input (`lock`, `price`, `reward`);
2. Phrase-Verfügbarkeit aus dem `answers[i]`-Eintrag, korrespondierenden `Flow_UnlockPhrase`-Nodes und
   Blacklist-Manipulationen.

Ein `null`-Input bedeutet nur, dass dort keine AnswerData serialisiert oder angeschlossen ist. Er bedeutet
nicht, dass die Option ohne Phrase- oder sonstige externe Voraussetzung angezeigt wird.

### Schritt D: Handler für Bedingungen, Effekte und Ziele

Handler liefern symbolische Werte, ausgangsspezifische Bedingungen, Zustandsänderungen oder Belohnungsfunde. Keine einzige große Funktion mit unübersichtlichen Sonderfällen bauen.

Erste Zieltypen:

- `Flow_DropItem` einschließlich dynamisch angeschlossener Item-/Mengenwerte;
- `Flow_AddRelation`, wobei positive Gewinne von null/negativen Änderungen unterschieden werden;
- Relationsgewinne über AnswerData/Flow_Answer.reward, einschließlich Inline-Daten;
- weitere im Inventar belegte Mechanismen für Einflussgewinn gezielt prüfen und entweder unterstützen oder als Abdeckungslücke nennen.

Erste benötigte Semantik:

- SmartRes und relevante konstante/Blackboard-Wertelieferanten;
- Param-/Player-Flags und Relationsvergleiche;
- Item-/Ressourcenprüfungen und Kosten;
- Taskzustände, Parameter-Setter und Relationsänderungen;
- `Flow_Talk.Text` als Gesprächszeile des konkreten Belohnungspfads;
- `Flow_AddPhraseToBlacklist` einschließlich des `remove`-Flags;
- `Flow_UnlockPhrase` als graphübergreifender Phrase-Freischaltkandidat;
- Phrase-/DLC-Prüfungen;
- echte Einstiegsevents, End-Nodes, Funktionsaufrufe und Rückkehr.

Verzögerte NPC-Interaktionen werden außerdem als belegte Zustands-/Eventkette verbunden, wenn innerhalb
desselben Graphen alle Glieder vorhanden sind: Ein `Flow_SetWGOParam` setzt einen konkreten Wert, ein
`Flow_ParamFlag` wählt damit nachweislich den passenden Ausgang, ein erreichbares
`Flow_AddInteractionEvent` registriert einen Eventnamen und ein gleichnamiger `CustomEvent` führt zu einem
`Flow_UnlockPhrase`. Die Hauptansicht erhält dafür eine eigene gerichtete Kante; Setter, Prüfzweig,
Interaktionsname, Eventeinstieg und vollständige lokale Zwischenpfade bleiben im Tooltip und in der
Detailansicht sichtbar. Bloße Namensgleichheit ohne passenden Parameterwert und Kontrollpfad reicht nicht.

Auch eigenständige `StartEvent`-Pfade mit `Flow_UnlockPhrase` werden als fachliche Knoten erhalten. Ihre
Taskzustände, Player-Parameter-Änderungen und tatsächlich benutzten Prüfzweige gehören in Tooltip und
Detailansicht. `Flow_SetPlayerParam` wird graphübergreifend mit passenden `Flow_PlayerFlag`-,
`Flow_PlayerParamCompare`- beziehungsweise `Flow_PlayerParamCompareInt`-Zweigen verbunden. Bei den beiden
Compare-Typen steht der Grenzwert im Node, während der tatsächlich gewählte Ausgang den Operator (`<`,
`==`, `!=` oder `>`) festlegt. `Flow_AddPlayerParam` darf bei unbekanntem Ausgangswert nur als gerichteter
Beitrag zu einer Bedingung markiert werden, nicht als Beweis, dass ein absoluter Schwellenwert erfüllt ist.
Der Graphfilter muss direkte Nachbarknoten aus anderen Dateien als Kontext erhalten, damit er keine
graphübergreifenden Kanten optisch verschwinden lässt.

Bekannte Ablaufknoten dürfen nicht als unklare Questverzweigung erscheinen. `Split` führt laut
dekompiliertem FlowCanvas-Code alle Ausgänge geordnet aus und `Flow_GoTo` steuert anhand von WGO, Ziel,
Geschwindigkeit und Pfadfindungsmethode nur eine Weltbewegung; beide werden deshalb als transparente
Ablaufknoten behandelt. `Flow_RendomFlow` ist dagegen eine echte Zufallsverzweigung. Deren gewählter
`true`-/`false`-Ausgang und die konfigurierte Chance bleiben als Pfadbedingung sichtbar, ohne eine
Uncertainty zu erzeugen.

`Flow_CreateItem` ist in den Exporten ein datenliefernder `SimplexNodeWrapper` ohne Flow-Eingang. Er erzeugt
ein `Item`-Objekt, vergibt es aber nicht selbst. Führt sein `Value`-Ausgang zu `Flow_DropItem.Item`, werden
Item-ID und Menge des erzeugten Objekts als Drop-Belohnung ausgewertet; unbenutzte Inline-Defaults des
Drop-Nodes dürfen diese Werte nicht überschreiben. Verwendungen desselben Datenwerts in Inventarprüfungen,
Entfernungen oder `Flow_AddItemToWGO` sind keine Belohnung.

Erreicht der Pfad einer Option eine weitere `Flow_MultiAnswer`, endet die fachliche Kette dort nicht.
Dabei werden jedoch nur echte Vorwärtsübergänge in eine tiefere Auswahl als gerichtete Auswahlkante
dargestellt. Der häufige Rücksprung aus einem Untermenü in ein bereits vorgelagertes NPC-Hauptmenü ist
Navigation und darf insbesondere keine Kante zu jeder dort angebotenen Gesprächsoption erzeugen.
Konvergieren mehrere Funde auf dasselbe nachfolgende MultiAnswer-Menü, führen sie in einen gemeinsamen
Menüknoten. Von diesem wird jedes Outcome genau einmal verbunden; ein kartesisches Produkt aus allen
Vorgängern und allen Antworten wird nicht dargestellt. Der Menüknoten weist darauf hin, dass die Auswahl
normalerweise erneut geöffnet werden kann und die ausgehenden Antworten daher nicht automatisch dauerhaft
gegenseitig ausschließend sind.

Der Ergebnisgraph wird außerdem in vier Inhaltsbereiche klassifiziert, räumlich getrennt und per Filter
unterscheidbar gemacht: `souls` in den fachlichen Kennungen gehört zu Better Call Soul, `refugee` zu Game
of Crone, `tr_` und nummerierte Cutscene-Kennungen wie `17cs` oder `18cs` zu Stranger Sins; alle übrigen
Funde gehören zum Base Game. Ein reiner DLC-Menüknoten übernimmt den Bereich seiner Nachbarn. Ein gemeinsam
genutztes NPC-Menü mit Nachbarn aus mehreren Bereichen bleibt als Base-Game-Infrastruktur eingeordnet.
Die vier Bereiche liegen als horizontale Bahnen im selben Netzwerk, damit graphübergreifende Kanten zwischen
Base Game und DLCs sichtbar bleiben. Innerhalb jeder Bahn wird der gerichtete Graph über seine stark
zusammenhängenden Komponenten in Abhängigkeitstiefen zerlegt und von links nach rechts angeordnet; Zyklen
teilen sich eine Spalte. Die HTML-Ansicht berechnet aus den gerade sichtbaren Knoten anschließend ein
kompaktes Layout neu: nicht belegte Tiefenspalten und vollständig ausgeblendete Inhaltsbahnen beanspruchen
keinen Leerraum, ohne die Links-rechts-Reihenfolge zu verändern. Farben kennzeichnen weiterhin den
Knotentyp und nicht die DLC-Zugehörigkeit.
Konservativ belegte, von Beginn an sichtbare Base-Game-Antworten ohne weitere Voraussetzung werden von einem
eigenen `START`-Knoten gespeist. Nicht belegte Wurzeln werden nicht künstlich an diesen Knoten gehängt.

Quest-Items aus Flow-Belohnungen werden außerdem mit den Item-Anforderungen externer GameData-Einstiege
verbunden. Für das Base-Game-Finale belegt `craft_data.json` zwei solche Konvergenzpunkte:
`craft_emitter` benötigt `fork_salty`, `mirror_of_pride` und `eternal_burning_coil`, `craft_barrel`
benötigt `sextant`, `endless_book` und `necklace`. Beide führen über ihr `end_script` zu `check_portal`;
dessen zweiter Abschluss startet `portal_activate_cutscene`, worin `Flow_RunScript skull_final` liegt.

Unteroptionen mit demselben fachlichen Outcome werden zu einem Ergebnisknoten zusammengefasst. Für die
Outcome-Gleichheit zählen Belohnungen, Taskzustände, freigeschaltete Phrases und andere Blacklist-Effekte;
die Blacklist der jeweils gewählten Antwort selbst ist dabei kein Unterschied. Die einzelnen
Antwort-Phrases, Voraussetzungen, Kosten, Gespräche und Funktionsaufrufe bleiben als Varianten im Tooltip
und in der Detailansicht erhalten. Abweichende Outcomes, insbesondere andere Belohnungen, bleiben getrennte
Knoten. Damit wird keine Belohnung als Folge einer vermeintlich exklusiven Dialogalternative verloren.
Reine Dialog-/Phrase-Relays ohne eigene Belohnung oder Taskänderung werden bis zum nächsten fachlichen
Outcome durchlaufen. Erreichen mehrere Menüantworten direkt oder über solche Relays dasselbe Outcome,
entsteht nur ein Ergebnisknoten; übersprungene Phrases und Gespräche bleiben als Variantenbeleg erhalten.
Eine belegte Rückkehrantwort zu einem übergeordneten MultiAnswer-Menü wird außerdem nicht als Questblatt
dargestellt, wenn sie ausschließlich eine bereits verwendete Dialog-Phrase blacklisted und keinerlei
Reward, Task-/Player-State, Phrase-Unlock, Script-/Event-Verbindung oder Unsicherheit besitzt. Damit bleiben
Dialognavigation und Questfortschritt getrennt, ohne unbekannte Enden pauschal auszublenden.
Wird dieselbe Phrase mit vollständig identischem ausführbarem Fund in mehreren MultiAnswer-Menüs angeboten,
entsteht ebenfalls nur ein fachlicher Knoten. Alle betreffenden MultiAnswer-Node-IDs bleiben als
Herkunftsliste im Tooltip und in der Detailansicht erhalten. Gleiche Anzeigenamen allein reichen für diese
Zusammenführung nicht; Voraussetzungen, Kosten, Gespräche, Effekte und Belohnungen müssen übereinstimmen.

Lokale Funktionsaufrufe werden nicht nur als UID-Sprung ausgewertet. Beim Eintritt über
`CustomFunctionCall._sourceOutputUID -> CustomFunctionEvent._UID` wird die gewöhnliche Fortsetzung des
konkreten Call-Nodes auf einem Call-Stack gesichert. Ein `Return` setzt anschließend genau diesen
Aufrufer fort. Das ist insbesondere bei mehrfach verwendeten Funktionen erforderlich und verhindert sowohl
lose Unlock-Knoten als auch falsche Rückkehrkanten zwischen verschiedenen Aufrufern. Die aufgelösten
Funktionsnamen sowie Call- und Event-Node-IDs bleiben in Tooltip und Detailansicht sichtbar.

Bekannt irrelevante Präsentations-Nodes dürfen nach Prüfung als Durchgang behandelt werden. Unbekannte Nodes sind keine automatisch bedingungslosen Durchgänge; falls zur Erfassung potenzieller Funde weiterverfolgt, bleibt der gesamte betreffende Pfad als unsicher markiert.

### Schritt E: Pfadbedingungen mit symbolischem Zustand ermitteln

Zunächst rückwärts den für eine Belohnung relevanten Teilgraphen eingrenzen, dann von bestätigten Einstiegen vorwärts auswerten. Der relevante Ausschnitt muss Datenabhängigkeiten und zustandsverändernde Vorgänger erhalten.

Ein Analysezustand enthält mindestens Kontrollposition, Aufrufkontext, symbolischen Zustand, Pfadbedingung und Herkunft. Bei Verzweigungen den Zustand aufteilen. Konjunktion gilt innerhalb eines Pfades, Disjunktion zwischen alternativen Pfaden.

Beispiele für korrekte Behandlung:

- Ein vor der Belohnung erforderliches Flag ist eine Vorbedingung.
- Ein erst auf demselben Pfad gesetztes Flag ist zunächst ein Effekt und kann eine spätere Prüfung erfüllen.
- Einfluss +10 vor einer späteren Einflussprüfung verändert deren Bezug zum Eingangszustand.
- Itempreis, Inventarprüfung und Itemabgabe werden für diese Auswertung einheitlich als Itemvoraussetzung
  dargestellt. Ob das Item anschließend verbraucht wird, ist für den gewünschten Questgraphen nicht relevant.
- `Flow_HasItemInInventory.Yes` ist eine Itemvoraussetzung. ID und Menge werden auch
  aus verbundenen Item-Erzeugern wie `Flow_CreateItem` aufgelöst. Der `No`-Ausgang gilt für die Questlogik als frei
  herstellbarer Pfad ohne Voraussetzung, da der Spieler das Item ablegen kann. In einer kompakten
  Zusammenfassung darf das Item nur dann als allgemein erforderlich erscheinen, wenn es auf allen
  alternativen Pfaden zum Fund benötigt wird.
- Task `Complete` als Setter ist kein Beweis, dass die Aufgabe schon vor dem Pfad abgeschlossen sein musste.

Ergebnisse auf einen klar benannten Einstieg beziehen: etwa Interaktion, Event oder Funktionsaufruf. Externe Auslöser bleiben externe Voraussetzungen. Für Flag-/Taskbedingungen einen ergänzenden graphübergreifenden Index ihrer Setter anbieten. Ein Setter-Kandidat ist noch kein Beweis für eine eindeutige Vorgängerquest; Besitzer/Objekt und Wert müssen zusammenpassen.

Bei CustomFunctionCall UIDs, Parameter, Rückkehr und Aufrufkontext beachten. Events nicht nur aufgrund gleichen Namens global verbinden; Empfänger und Auslösung prüfen. Unaufgelöste Aufrufe/Events explizit melden.

Die für die Hauptausgabe relevante Pfadprojektion läuft von einer konkreten MultiAnswer-Option bis zu einer
konkreten Belohnung. Aus diesem Ausschnitt werden fachliche Sammlungen gebildet, ohne die Zuordnung zum Pfad
zu verlieren:

- alle `Flow_Talk.Text`-Werte als `conversations`;
- alle `Flow_SetTaskState`-Werte als `task_states`;
- alle Blacklist-Änderungen als getrennte Hinzufügen-/Entfernen-Listen;
- direkte und AnswerData-basierte Belohnungen;
- alle Bedingungen vor und am MultiAnswer-Input sowie externe Phrase-Freischaltungen.

Wenn mehrere Optionen oder alternative Kontrollpfade dieselbe Belohnung erreichen, dürfen ihre Gespräche,
Taskänderungen und Bedingungen nicht vermischt werden. Jeder fachlich unterschiedliche Pfad erhält einen
eigenen Eintrag oder klar getrennte Alternativen.

### Schritt F: Schleifen und Begrenzung

Dialoge besitzen Menü-Rücksprünge. Ein globales „Node besucht“ würde gültige alternative Zustände verlieren. Wiedererkennung daher auf Node plus relevantem Zustand und Aufrufkontext beziehen.

- Gleichwertige Zustände/Pfade zusammenführen.
- Nur nachweislich widersprüchliche Pfade verwerfen.
- Bedingungen nur semantisch sicher vereinfachen.
- Wiederholbare Gewinne nicht beliebig oft aufsummieren; wiederholbare oder unbeschränkte Änderungen gesondert kennzeichnen.
- Konfigurierbare Grenzen für Zustände, Rekursion und Pfadmenge setzen.
- Jede erreichte Grenze im betroffenen Ergebnis und in der Übersicht als Unvollständigkeit melden.

Vollständige mathematische Lösung beliebiger Spielskripte ist kein Abnahmekriterium. Vollständige Offenlegung der Grenzen ist eines.

### Schritt G: Markdown-Berichte und Zuordnungshilfen

Deterministisch sortierte, kompakte Berichte im Format aus Abschnitt 1.1 rendern. Gesprächs-, Task- und
Phrase-Listen sind primäre Daten und keine versteckten Details. Kurze Belegpfade und Node-IDs werden nur in
einer optionalen Diagnoseansicht ausgegeben. Eine Übersicht enthält Counts für gefundene, vollständig
analysierte, teilweise analysierte und keinem Einstieg zugeordnete Belohnungsstellen. Kein Fund darf still verschwinden.

APWorld-Zuordnung nur anhand bestehender Daten und belegter Zusammenhänge vorschlagen. Spiel-ID, vermuteter APWorld-Key und Begründung getrennt zeigen. Unbekannte Keys nicht erfinden. Mengen, negative Bedingungen und alternative Pfade im Bericht erhalten.

Das aktuelle `CanComplete` verknüpft Anforderungen mit UND; `QuestEventData` besitzt Mengen von Keys, keine allgemeine boolesche Formel und keine Itemmengen pro Voraussetzung. Deshalb OR-Pfade, Verbrauch, Mengen und zeitabhängige Zustände nicht verlustbehaftet in die vorhandenen Felder pressen. Solche Modellierungsentscheidungen verbleiben beim Benutzer.

## 6. Vorgeschlagene Ablage und Bedienung

Analysewerkzeug: `worlds/graveyard_keeper/tools/flow_analysis/`, aufgeteilt nach Parser, Modell, Node-Semantik, Analyse und Markdown-Ausgabe. Die genaue Anzahl Module klein halten. Erforderliche `__init__.py` berücksichtigen.

Tests: `worlds/graveyard_keeper/test/flow_analysis/` mit kleinen selbständigen Fixtures. Große vollständige Dumps nicht zusätzlich ins Repository kopieren. Reale Referenzausschnitte minimal und nachvollziehbar übernehmen.

Ausgabevorschlag: `worlds/graveyard_keeper/dumps/quest_analysis/`. Dieses Verzeichnis ist Entwicklungsdaten-Ablage; `dumps/` wird bereits durch `.apignore` vom APWorld-Paket ausgeschlossen. Lokale Ignore-Regeln prüfen und in der Übergabe deutlich sagen, ob erzeugte Berichte versioniert sind. Werkzeug und Tests ebenfalls hinsichtlich APWorld-Packaging prüfen, ohne unnötige Produktänderungen.

CLI soll mindestens erlauben:

- Eingabeverzeichnis und Ausgabeverzeichnis;
- Graph-/NPC-Filter mit klar dokumentierter Bedeutung;
- Filter nach Item, Node oder Zieltyp;
- Analysegrenzen und Ausgabe einer Zusammenfassung.

Ein einziger dokumentierter Aufruf muss die Berichte neu erzeugen können. Keine fest eingebauten Benutzerpfade; lokale absolute Pfade nur in Nutzungsbeispielen. Bei optionalem Modulstart vermeiden, dass unnötig die gesamte APWorld geladen werden muss; den tatsächlichen Einstieg entsprechend prüfen. JSON-Export ist kein Pflichtfeature.

## 7. Tests und Prüfung am echten Material

Verpflichtende kleine Tests:

- `$id`/`$ref`, Wrapper, Werte, ungültige Referenzen und doppelte Kanten;
- Flow-/Datenfluss-Trennung;
- MultiAnswer-Indizes 0, 1, 2 und 10, veränderte Verbindungsreihenfolge, dekorierte Ports;
- Inline- und verbundene AnswerData sowie belegter Vorrang gegenüber Defaults;
- getrennte `lock`-/`price`-/`reward`-Interpretation;
- direkte ItemDrops, direkte Relationsänderungen, Relationsgewinn über Answer;
- NPC-Kontext vorhanden, explizit abweichend und unbekannt;
- positive und negative Flagzweige, UND innerhalb und ODER zwischen Pfaden;
- Setter vor Prüfung, Einflussänderung vor Prüfung, Itemverbrauch;
- Funktionsaufruf/Rückkehr, externer Eventkontext;
- `CustomFunctionCall._sourceOutputUID` wird mit genau dem passenden `CustomFunctionEvent._UID` verbunden;
- Gespräche, Task-State-Änderungen und Blacklist-Manipulationen zwischen Option und Belohnung werden
  vollständig und nur diesem Pfad zugeordnet;
- `remove = false` und `remove = true` bei `Flow_AddPhraseToBlacklist` landen in getrennten Ausgabefeldern;
- MultiAnswer-Option mit `null`-AnswerData behält trotzdem eine mögliche Phrase-Anforderung;
- jede nichtleere Phrase wird als `required_quests` erfasst und mit graphübergreifenden
  `Flow_UnlockPhrase`-Quellen verknüpft, unabhängig von einem führenden `@`;
- Menüschleife ohne Änderung und Schleife mit Änderung;
- unbekannter Node und erreichte Analysegrenze ergeben unvollständige Ergebnisse;
- stabile Ausgabe und keine verlorenen Zielstellen.

Referenzprüfung am Astrologen:

1. Mapping und Werte für Option #3 / Answer 476 wie oben wiederfinden.
2. Schlüssel-Drop 163 mit seinen tatsächlichen vorgelagerten Bedingungen untersuchen.
3. Direkte Relations-Nodes und Answer-basierte Gewinne im Bericht erhalten.
4. Für `@astrologer_charm_no` exakt die acht Gespräche, beide Task-State-Änderungen, den
   Blacklist-Eintrag und `Flow_AddRelation` +10 in der kompakten Hauptausgabe wiederfinden.
5. Den Übergang `44.out_7 -> Call 292 -> Event 748` per UID belegen.
6. `npc_actress.json`, `Flow_UnlockPhrase` 371, als graphübergreifende Quelle der Voraussetzung
   `astrologer_charm_no` aufführen.
7. Mindestens einen vollständigen Pfad einschließlich negativer Zweige manuell gegen den Dump prüfen.
8. Danach mindestens einen weiteren NPC und einen graphübergreifenden beziehungsweise extern ausgelösten Fall prüfen.

Da dieses Werkzeug ausschließlich unter `tools/flow_analysis` arbeitet, wird nur seine fokussierte Testsuite
ausgeführt. Weder `pytest` noch die gesamte Graveyard-Keeper- beziehungsweise Archipelago-Testsuite sind für
diese Analysearbeit vorgesehen:

Die Tests werden gemäß `docs/tests.md` als runner-agnostische `unittest.TestCase`-Klassen geschrieben.
Keine pytest-spezifischen Fixtures, Marker, Assertions oder Parametrisierungen verwenden. Für diese Arbeit
wird auch der Testlauf selbst mit `unittest` dokumentiert.

```text
python ModuleUpdate.py
python -m unittest discover -s worlds/graveyard_keeper/test/flow_analysis -t .
```

Falls die endgültige Testablage abweicht, den dokumentierten Aufruf anpassen. Tatsächliche Ergebnisse und vorbestehende Fehler berichten; kein Erfolg allein aufgrund erzeugter Markdown-Dateien behaupten.

## 8. Lieferreihenfolge und Abnahmekriterien

### Meilenstein 1: Belastbare Options- und Belohnungsextraktion

Parser, Datenauflösung, MultiAnswer-Mapping, Belohnungsinventar und erster Astrologen-Markdown-Bericht. Noch nicht ermittelte vorgelagerte Bedingungen deutlich markieren. Zugehörige Parser-/Mapping-Tests bestehen.

### Meilenstein 2: Pfadbedingungen

Kontrollfluss, Zweige, Zustandsänderungen, bestätigte Aufrufsemantik und Schleifenbehandlung ergänzen. Der Bericht unterscheidet vollständige und teilweise Ergebnisse und zeigt Belegpfade.

### Meilenstein 3: Gesamtauswertung und Übergabe

Alle Dumps auswerten, Abdeckung und verbleibende Grenzen zusammenfassen, Markdown nach Graph/NPC aufbereiten und vorsichtige APWorld-Zuordnungsvorschläge ergänzen. Dokumentierten Aufruf und Testresultate liefern.

Die Aufgabe ist erfüllt, wenn:

- Markdown-Dateien zur manuellen Questdatenpflege vorhanden und verständlich sind;
- ItemDrops und erkannte Einflussgewinne einschließlich Answer-Belohnungen systematisch erfasst werden;
- MultiAnswer-Optionen korrekt ihren Voraussetzungen und Ausgängen zugeordnet sind;
- alternative Wege, Kosten und Effekte unterscheidbar bleiben;
- pro Belohnungsoption Gespräche, Task-State-Änderungen und Phrase-Blacklist kompakt und direkt lesbar sind;
- UID-verknüpfte CustomFunctionCall-/CustomFunctionEvent-Paare nicht als Unterbrechung des Pfads erscheinen;
- Phrase-Freischaltungen und MultiAnswer-Input-Anforderungen getrennt, aber gemeinsam im Fund dargestellt werden;
- jeder Fund Belege und einen ehrlichen Vollständigkeitsstatus besitzt;
- ungeklärte Semantik und nicht unterstützte Mechanismen sichtbar sind;
- die relevanten Tests ausgeführt und ihre Ergebnisse dokumentiert wurden;
- produktive Questdaten und Clientvertrag unverändert bleiben.

## 8.1 Ergänzung: vollständige Quellextraktion

Der frühere Client-Dump exportierte ausschließlich `Resources.LoadAll<FlowScript>("FlowCanvas")` und
verwarf bei `Graph.Serialize(..., null)` die Unity-Objektreferenzen. Dadurch fehlten 34 `FlowMacros`, und
`MacroNodeWrapper._macro` erschien nur als bedeutungslose Zahl. Der Dump-Modus exportiert nun zusätzlich
`Resources.LoadAll<Macro>("FlowMacros")`, benennt diese Dateien mit `macro__` und schreibt pro Graph eine
`_unityObjectReferences`-Tabelle mit Index, Objektname und Typ. Der Export läuft in `Plugin.Awake()`, sodass
das Hauptmenü genügt und kein Spielstand geladen werden muss.

`GameBalance` wird dabei direkt aus der unveränderten Ressource `game_data` nach
`VanillaGameDataExports` geschrieben. Fehler einzelner heterogener Felder werden isoliert protokolliert,
statt den gesamten Dump abzubrechen. Der so verifizierte Vanilla-Dump bestätigt, dass alle
`TechDefinition.phrases`-Listen leer sind; fehlende Phrase-Quellen dürfen daher nicht pauschal als
Technologie-Unlocks erfunden werden.

Die zusätzlichen Makros lösen die zuvor offenen Quellen für `refugee_tanner_4_1`, `refugees_s26_1`,
`refugee_s26_3` und `souls_s_s6_a_repaired_ask` auf. `stone_statues` bleibt nach exakter Suche in allen
FlowScripts, FlowMacros, Vanilla-GameBalance-Daten und im dekompilierten Quellcode ohne Unlock-Quelle.
Dieser Fall ist als wahrscheinlich tote/fehlerhafte Dialogoption zu kennzeichnen, solange kein weiterer
serialisierter Datenträger oder Laufzeitbeleg das Gegenteil zeigt.

Ein Offline-Export ohne Spielstart ist grundsätzlich möglich, da die Unity-Dateien nicht verschlüsselt
sind. Dafür muss ein Werkzeug wie AssetRipper/AssetStudio jedoch die exakt passenden Managed Assemblies
verwenden, die benutzerdefinierten `MonoBehaviour`-/`ScriptableObject`-Layouts deserialisieren und
PPtr-/Unity-Objektreferenzen erhalten. Der vorhandene reine Ressourcen-/Namensexport genügt dafür nicht.

## 9. Einstieg für den umsetzenden Chat

Dieses Dokument und die geltenden AGENTS.md lesen, Arbeitsstand prüfen, Setup durchführen. Anschließend die belegten Astrologen-Ausschnitte selbst nachvollziehen, Node-Inventar erstellen und offene Semantik gezielt prüfen. Mit Meilenstein 1 beginnen und bis zur Gesamtauswertung fortfahren. Nicht erneut grundsätzlich nach dem Ausgabeformat fragen: Markdown zur manuellen Übertragung ist ausdrücklich gewünscht.
