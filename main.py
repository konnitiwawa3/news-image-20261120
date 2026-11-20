"""Render the 20 November 2026 front page as a deterministic PNG."""

import base64
import functools
import json
import math
import os
from pathlib import Path
import struct
import zlib


SIZE = 1024
SCALE = 3
# Astryx Neutral light palette. Edges and type are supersampled on the same grid.
PALETTE = (
    (255, 255, 255), (17, 17, 17), (71, 71, 71), (212, 212, 212),
    (241, 241, 241), (0, 57, 120), (185, 215, 255), (138, 0, 17),
    (255, 196, 190), (226, 226, 226),
)
PAPER, INK, MUTED, RULE, WASH, BLUE, PALE_BLUE, RED, PALE_RED, LAND = range(len(PALETTE))

LEADS = (
    ("SHENZHEN, CHINA", "TRUMP, XI AND PUTIN HOLD\nFIRST THREE-WAY SUMMIT",
     "The leaders of the US, China and Russia met in Shenzhen and signed a four-point peace declaration covering nuclear risk, UN reform, energy stability and the ICC. Europe and Ukraine were not at the table."),
    ("THE HAGUE", "WORLD COURT RULES\nMYANMAR COMMITTED GENOCIDE",
     "The ICJ ruled 9-6 that Myanmar's 2017 campaign against the Rohingya was genocide, the court's first such finding against a state. More than 1.3 million Rohingya remain displaced."),
)
CARDS = (
    ("RIYADH, SAUDI ARABIA", "HOUTHI MISSILE\nDAMAGES RIYADH TOWER",
     "Missiles hit the financial district and damaged the Public Investment Fund tower. No injuries were reported."),
    ("KERCH STRAIT, CRIMEA", "CRIMEA BRIDGE HIT FOR\nTHIRD TIME IN A WEEK",
     "Ukraine struck the bridge again and halted rail traffic. Putin vowed a far harsher response."),
    ("NEW YORK, US", "ANTHROPIC RAISES\n$81.3B IN RECORD IPO",
     "The AI firm's shares closed 17% above the offer price near $97. The debut did not revive a weak AI trade."),
)
MARKETS = (
    ("S&P 500", "-2.0%"), ("NIKKEI 225", "-4.8%"), ("GOLD", "-4.2%"),
    ("BRENT", "$90.05 +0.7%"), ("US 10Y YIELD", "ABOVE 5%"),
)
FOOTNOTE = (
    "Compiled from BBC, Reuters, AP, Al Jazeera, SCMP, France 24, The Hindu and others.",
    "REPORTED = confirmed by multiple outlets. CLAIM = a single source or an official claim. "
    "FORECAST = expected or planned.",
)

# Rows are under the map in this order. Coordinates are (longitude, latitude).
# Off-world briefs use the space panel. UN headquarters is plotted in New York.
BRIEFS = (
    ('KYIV, UKRAINE', 'Russian barrage damages the Austrian and Dutch embassies and a cathedral in the capital.', 'REPORTED', (30.52, 50.45)),
    ('BERLIN, GERMANY', "Ukraine's allies meet and say Europe is ready to talk with Russia.", 'REPORTED', (13.4, 52.52)),
    ('STRAIT OF HORMUZ', "Tanker attacks intensify in the war's ninth month; the US cost is put at $48.3B.", 'REPORTED', (56.44, 26.56)),
    ('CENTRAL GAZA', 'Israeli troops cross the Yellow Line in the first incursion since the truce.', 'REPORTED', (34.37, 31.42)),
    ('ANTALYA, TURKEY', 'COP31 draft drops the call to phase out fossil fuels as talks run overtime.', 'REPORTED', (30.71, 36.9)),
    ('WASHINGTON, US', 'White House fires cyber director Sean Cairncross after a week of tech outages.', 'REPORTED', (-77.04, 38.9)),
    ('SANTA CLARA, US', 'California opens a probe into Nvidia after CEO Jensen Huang resigns.', 'REPORTED', (-121.96, 37.35)),
    ('BRUSSELS, BELGIUM', 'UK and EU seal food and youth mobility deals at their summit.', 'REPORTED', (4.35, 50.85)),
    ('WASHINGTON, US', 'Trump says he is in no rush on new Iran strikes and looks to 2027.', 'REPORTED', (-77.04, 38.9)),
    ('PORT-AU-PRINCE, HAITI', 'Police raid in Martissant kills 34 suspected gang members.', 'REPORTED', (-72.33, 18.54)),
    ('NAIROBI, KENYA', 'Kenya discharges its last Ebola patient, 37 days after the first case.', 'REPORTED', (36.82, -1.29)),
    ('INTERSTELLAR SPACE', 'Voyager 1 reaches one light-day from Earth, 49 years after launch.', 'REPORTED', None),
    ('MERCURY', 'BepiColombo enters Mercury orbit after an eight-year journey.', 'REPORTED', None),
    ('TOKYO, JAPAN', "Core inflation hits the year's high; a rate hike stays on track.", 'REPORTED', (139.69, 35.68)),
    ('BRASILIA, BRAZIL', 'Central bank sells $1B to slow the dollar; the real is down 18% in a month.', 'REPORTED', (-47.88, -15.79)),
    ('MRIMA HILL, KENYA', 'US consortium wins the $60B critical minerals deal over Chinese rivals.', 'REPORTED', (39.25, -4.49)),
    ('YENNE, SENEGAL', 'Dozens are missing after a migrant boat capsizes off the coast.', 'REPORTED', (-17.19, 14.63)),
    ('CARACAS, VENEZUELA', 'The US and Venezuela sign a military cooperation deal.', 'REPORTED', (-66.9, 10.48)),
    ('SOUTH KORDOFAN, SUDAN', 'A drone strike on a gold mine kills 10 people.', 'REPORTED', (29.7, 11.12)),
    ('DHAKA, BANGLADESH', "Arson and protests flare ahead of ousted PM Hasina's planned return.", 'REPORTED', (90.41, 23.81)),
    ('UNITED NATIONS', 'The secretary-general race stalls after eight rounds of voting.', 'REPORTED', (-73.97, 40.75)),
    ('COPENHAGEN, DENMARK', 'Parliament ratifies the Greenland security deal with the US.', 'REPORTED', (12.57, 55.68)),
    ('TALLINN, ESTONIA', 'Estonia will close its border with Russia for at least six months.', 'REPORTED', (24.75, 59.44)),
    ('GEORGIA, CAUCASUS', 'A gas blast collapses part of a housing block and kills six.', 'REPORTED', (44.8, 41.72)),
    ('PARIS, FRANCE', 'IEA calls the Iran war the biggest threat to energy security in history.', 'REPORTED', (2.35, 48.86)),
    ('WASHINGTON, US', 'The Senate passes an energy permitting overhaul, 62 to 33.', 'REPORTED', (-77.04, 38.9)),
    ('NEW YORK, US', 'IMF warns global debt will soon near 100% of world GDP.', 'REPORTED', (-74.01, 40.71)),
    ('ODISHA, INDIA', 'Cyclone Akvan makes landfall; 372,000 people are sheltered.', 'REPORTED', (86.35, 20.32)),
    ('SUVA, FIJI', 'Fiji and Tonga declare disasters as El Nino drought worsens.', 'REPORTED', (178.44, -18.14)),
    ('LOS ANGELES, US', 'An El Nino storm threatens flooding and mudslides.', 'FORECAST', (-118.24, 34.05)),
    ('YONGBYON, NORTH KOREA', 'The IAEA says the uranium enrichment plant is expanding.', 'REPORTED', (125.75, 39.8)),
    ('KHYBER, PAKISTAN', 'The army says 22 militants were killed in border raids.', 'CLAIM', (71.15, 34.12)),
    ('EDINBURGH, SCOTLAND', "GTA VI's launch tops $2.3B in sales, a record entertainment debut.", 'REPORTED', (-3.19, 55.95)),
    ('SEOUL, SOUTH KOREA', 'A court orders a retrial of ex-PM Han in the martial law case.', 'REPORTED', (126.98, 37.57)),
    ('ULAANBAATAR, MONGOLIA', 'President Khurelsukh resigns; the speaker takes over as acting president.', 'REPORTED', (106.9, 47.92)),
    ('MOGADISHU, SOMALIA', 'Somalia expels the UAE ambassador in a sovereignty row.', 'REPORTED', (45.32, 2.05)),
    ('SHENZHEN, CHINA', 'The Philippines and Chile sign a free trade deal at APEC.', 'REPORTED', (114.06, 22.54)),
    ('SYDNEY, AUSTRALIA', 'Marathon champion Jepchirchir is banned three years for doping.', 'REPORTED', (151.21, -33.87)),
    ('ZURICH, SWITZERLAND', 'Young people in 25+ countries plan a strike over living costs.', 'FORECAST', (8.54, 47.38)),
    ('ROME, ITALY', 'Italy fines Meta 805 million euros, according to reports.', 'CLAIM', (12.5, 41.9)),
)

# Coarse, hand-drawn coastlines in longitude/latitude, split at the map seam.
COASTS = (
    ((-168, 66), (-158, 71), (-138, 69), (-125, 72), (-108, 73), (-94, 75),
     (-78, 72), (-64, 60), (-61, 51), (-54, 48), (-66, 44), (-75, 37),
     (-81, 26), (-84, 28), (-89, 30), (-97, 26), (-97, 19), (-91, 18),
     (-87, 21), (-88, 15), (-82, 9), (-77, 8), (-79, 7), (-85, 10),
     (-95, 16), (-104, 20), (-112, 28), (-114, 27), (-118, 33),
     (-124, 41), (-124, 49), (-132, 55), (-140, 60), (-151, 59), (-163, 55),
     (-166, 59), (-157, 63)),
    ((-81, 10), (-73, 12), (-65, 11), (-60, 8), (-51, 4), (-48, -1),
     (-36, -5), (-34, -9), (-40, -20), (-46, -24), (-53, -33), (-58, -39),
     (-65, -45), (-68, -55), (-73, -53), (-75, -43), (-72, -31), (-70, -20),
     (-75, -14), (-81, -6), (-79, 1)),
    ((-73, 78), (-60, 82), (-25, 82), (-15, 76), (-24, 66), (-42, 60),
     (-50, 63), (-58, 70)),
    ((-115, 76), (-102, 81), (-82, 83), (-66, 80), (-76, 74), (-91, 74)),
    ((-85, 61), (-74, 58), (-63, 62), (-64, 68), (-77, 70), (-84, 66)),
    ((-18, 65), (-14, 67), (-24, 66), (-23, 63), (-16, 63)),
    ((-10, 36), (-10, 44), (-2, 43), (-5, 48), (3, 51), (8, 54), (10, 57),
     (8, 58), (5, 62), (16, 69), (26, 71), (33, 70), (29, 64), (22, 61),
     (23, 57), (29, 60), (39, 65), (42, 68), (56, 69), (65, 72), (80, 73),
     (100, 78), (117, 73), (137, 72), (155, 71), (178, 70), (179, 64),
     (164, 62), (158, 54), (160, 50), (153, 52), (147, 59), (137, 56),
     (140, 49), (131, 43), (129, 40), (129, 35), (125, 37), (124, 40),
     (119, 39), (122, 32), (119, 26), (111, 21), (108, 21), (109, 14),
     (106, 9), (103, 9), (104, 2), (100, 5), (97, 15), (92, 21),
     (88, 22), (84, 19), (80, 15), (77, 8), (74, 11), (72, 18),
     (67, 24), (59, 25), (55, 24), (58, 20), (53, 16), (44, 12),
     (41, 18), (36, 28), (33, 32), (35, 35), (28, 36), (27, 41),
     (32, 44), (39, 44), (39, 47), (31, 46), (29, 42), (24, 40),
     (24, 35), (20, 39), (15, 44), (12, 44), (17, 39), (15, 38),
     (10, 43), (6, 43), (3, 42), (0, 39), (-6, 36)),
    ((-6, 36), (4, 37), (11, 36), (12, 33), (21, 32), (31, 31),
     (34, 28), (37, 21), (43, 12), (51, 12), (47, 5), (42, -1),
     (40, -10), (40, -16), (35, -21), (32, -29), (25, -34), (18, -35),
     (14, -30), (12, -18), (12, -7), (9, 0), (9, 4), (3, 5),
     (-8, 5), (-13, 9), (-17, 15), (-16, 22), (-13, 27), (-10, 30)),
    ((49, -13), (50, -16), (47, -24), (44, -26), (43, -23), (44, -18)),
    ((-8, 51), (-5, 55), (-6, 58), (-3, 59), (0, 52), (1, 51), (-5, 50)),
    ((-11, 51), (-10, 54), (-7, 55), (-6, 52)),
    ((129, 32), (132, 34), (138, 36), (141, 41), (143, 45), (146, 44),
     (143, 40), (141, 36), (137, 34), (132, 32)),
    ((120, 19), (122, 18), (125, 9), (124, 6), (122, 9), (120, 13)),
    ((95, 5), (101, 2), (107, -6), (115, -8), (108, -8), (101, -4)),
    ((109, 1), (117, 7), (119, 4), (117, -4), (111, -4)),
    ((131, -2), (142, -4), (151, -10), (145, -10), (137, -6), (131, -3)),
    ((113, -22), (117, -19), (122, -18), (126, -14), (132, -12),
     (137, -13), (136, -16), (141, -17), (143, -11), (146, -17),
     (153, -27), (150, -35), (146, -39), (138, -36), (131, -32),
     (126, -32), (116, -35), (114, -29)),
    ((166, -45), (171, -41), (177, -38), (175, -42), (169, -47)),
    ((-85, 22), (-79, 23), (-74, 20), (-79, 20)),
    ((-73, 20), (-69, 20), (-68, 18), (-72, 18)),
)

# Fixed offsets keep labels legible while the fine leaders retain the true positions.
EUROPE = {1: (11, -1), 2: (15, -9), 5: (12, -2), 8: (-10, -8),
          22: (0, -14), 23: (10, -6), 25: (-16, 4), 33: (-7, -10),
          39: (-7, 11), 40: (10, 7)}
US_EAST = {6: (-18, -8), 9: (-10, 14), 21: (-4, -14),
           26: (12, 11), 27: (19, -2)}
WORLD = {3: (14, -1), 4: (-10, -13), 7: (-14, -14), 10: (-9, -14),
         11: (-4, -12), 14: (19, 1), 15: (9, 7), 16: (-10, 12),
         17: (-9, 5), 18: (17, 13), 19: (-19, -6), 20: (15, 3),
         24: (2, -12), 28: (2, 16), 29: (-9, 13), 30: (15, 9),
         31: (7, -13), 32: (4, -12), 34: (-13, -3), 35: (-8, -14),
         36: (12, 10), 37: (9, 12), 38: (12, 8)}

# Monochrome glyph masks measured at 3×, compressed with their metrics. The
# Source Sans 3 and Newsreader license notices are in fonts/.
FONT_DATA = (
    'c-ri}+p=uERUiH;u**OwwqvQ)tEILpMR73Z7%=$n0RPGbOG^p_6B`U9hDuc`Z;|WV=05j43Qv-jG|tlOp1n?cZ~Obc-8#(GJ*TD)'
    'Lqp^68~^;_@rO@8@rMuJ{O1pU@!^~QzdwI;AHVL?$4lXoesG~C=X|aCk``Z_bIG;TxhT@=`j=Y0rM{-vzTf^Da!->=+jny4-yFZn'
    'm+K$?<Hrw=mo^++Ys2B;<E3y(Klt1pu`liIthI<XTpoA%>qz(ilfP>BsjkwUbL*4V+T409Vvn6hk6j*o>4kFnesN{AtbH!GT7Tg0'
    'y>HuZ+HWuSX!n0w^oAQh+mrg*(#wdXcIQhfdn1f=_do6pyc^s(w5PPz7Bzno_lE25)PHqJ`>cSw$w$<7H%RB#5u*(AulBju=iB8e'
    'd5lPHZScLvF2iy7cu6mF`0|6+05KZ!(<XQOtp0Y-r#=5anKjf$Y%HJH)7r+_m$3q%Cphib$9FE@Z*SXQ&uz_j=!yQN-gB*A_2h-#'
    'Ep6P!{Jq>6=I>v=aJ9wu=1+RXC%bxHC2g(!t4nJWG&YU4rjSGSeTKC5-2T7a=Rf!ReEraG<lV<`xQx*Ws95`)oc=Gq(Fdj_j>ccN'
    'xq~n0)7_&1ecxwRpJjQ_mQD&9fo+tlrB9`&Otc4~@Fff?pZN~3W}>)1jK&XIYjN(Jsj+YNfx&5y{+r9AgM&pDd?z%0GPVV9nU0|?'
    '=9+3-M{P>BJ{b*<@0PcA{uf$aZ8ROX^Bot>4;O8iiLw_&nKp*okC4@Z8w1_h<HY`vX~UQ+Z?jdW#a6w45w+I-?V`2sxs~qU;9G0|'
    't}VlW8%}^ZR#RKvezep1^85|$$L;<Pc>jkne`2FrmuFl^uVQ5i40`MOzR9#PCI%-T8X3C$BDBeW`A)n4-&6Y!$JYK!`k`;|i%;9@'
    '`+mRi_p6`5EObKBp8F5WwfXvM5Y|N*{Zb!$H^JEbqhcRpZ$s=Yg@4E{7fOL31Bs^8l|CtC8bjZ@BB!Bn+Bt{ThX307;e`Egf;NoV'
    '9n;7|x^!C4Lme%GJdgac#e{@;Z(kgF8M!Ob=boSZQ*Uk2`DH$hypwRwL#EB~zqP(PX;%BvKbLoH+g97ILa(_R$NR?7UHyGqxwLr`'
    '`*zqi#+J7CyL_{@`~Sp@MO*dP$HGrz;R>X!?I#!o9*ZzWp_);^R1zbx&c)D0qEY{}Se2Jml|$z-JE=+zxNTbgtvA}`=+vJA{^Ii6'
    '_G$P3wZX=I-S=gA@MBr_Jy@mTF_|>>H<0PzW{abA=6((D-=`iN9O-M7eu%ef4gK{teLav5XeXRjJ69~ZmYo|(O|&gBN8R3}^fYdy'
    'mA})zKYrWq)7tqPs-151XQxMSItY2(%4Im;%$w6)d&BY$?aoJhN*F9&e|m38Yv*sab{?>u2kg(p8>*9i;$_d29lf-bPIpiv!i)lv'
    'gKyJ0t8E)+Z0G3n(L(3$Pw^?mJ^v2WhStvCVxIokdHT<#ordZ8P8;{2#~t?Y@t84NVm};hP^~Mou~tqmHyNp#1LNjJP~6KCY2bTH'
    'T04KcweyJW9PGk#=9@`tBNmXp_-?J8zr&}a<Hs{K^DRH^vA;{ZSetGUhVkW7<T+`8eJFOuwr>}m)U<Z~-imDJHVcTfu;^{qkrrlZ'
    'Paiw^KlgMcZqY{=-T{gr<bzB6{Y8I%n%=xlX8wS<xYnPi(N5g@D{|({p<^Cpeqq5*kQbR>SU1Q!7sq+@irb?+JUX3M;FOBaNkEEX'
    '1}F3OUjJT^r9kh61f#tZr~Uk0+c3Ab$1doIz5TJzli24>PgCavGpD}uhJ!<FJY<_EBOS5>k@`B#lRs2s>4@ZWoPzuLE_ESff3bq3'
    'qVb@djyb(Qo$tWpvlVin9kaKjweyd5uuIoBcDY51jd}<dE2#=zxE+1h_UHL?=+CVB(+Xh+x86zI<#5~H;*YQPc6!C$UWn`@#oMHH'
    'gNgnV76TJAHAL!-aQA~mKf^k|ErcHDfqwGuvVs2FLK4QoO27`Fr1_MNn|l&h_xqH7A7J{vw_y4%CziJ2>tJJx&<}i?w6*j9TT!i-'
    'Gby`MI75toz|o|B%o_uPhm!B>Q{Fh0)a3!K&p9c>nh$7^CZ9O#!I8L5r^0bCR_Dj*bV)*r|Ij)Vx#+{-qQ}DQGqaO{mM4)nesjn#'
    'JmycSuY$|wF!FQmiy?5{m&j!o>w+81<B+I`JVwmBP-EnmUhVmXHU!LvZgU*pP2S$?PgfIK$`iG2X!K{{K0Ig9d&%}*72<|RA&dYa'
    '1)s+|v0y!Ig0UXs-rD(RgAIa-0u8Mw6xooD2pLsZENJP}mR#!j8%JyCpG!&x6WVv$;DJJ*R3&NUwK~p(>5KKgFHQ%f(4Rii)=sxL'
    '7Q%pm+D{D+PlC(9xch|7v+UU{T3D!3>DXJ++UdESU9@~jKfvpaEwGC8UFa+Admyklta?%~3ZZY?gEAg&JYdJrN{QY0%JfIL+*=r_'
    'oncoygH~~0ZDC9xx1r57X!W=?(ulnWn4w8s`d3-a+}e3ujySxNNXI<sQrj@nvlRJ}G!*zM!Cis4taCsk-M`3N3m+COyjvhrS@Py{'
    'D7X5}^dSo??6%rlcv_9MLw>3c-B@=Aw-WX(1SoxmJa#!uRm6Hrvqb4Ix43);CzYjME-rdfiefc|bXNsFvXf3%r|>=WJgs^%FpoKQ'
    '7Mxu|Pcmyu#+(H9z49HpJ~ku}KvgO7*Z=UIMrzvIdEQ*zV`Ysq2F(BDq_C@OJgb6!r9CU6iInN+W#@X3=&$51KX++o6KA-OE&b3g'
    '{oBi>&Vn>8J}B{9590@y-ADZ1vDr*`4+4hDA8FS>iUlyCXm|J}yu)shm`m<O|Fx(7>;L#)^ju}AQ25hl>}lB9pskj7FMsye$r@>N'
    '*(LoDIwO#G{r;QS^2?Muql$7Gom>BHjp(=3-474XySsgY7fM$g$37Lsd;LOV({L&T(1x_tn1?Bs?~A2S9{R+Jl%GtVNA59Coq;XE'
    '*V6Nln{+pyx|Xu0(~v;Btn<syVB|+0AU{BUa{c$NogHe=ecx|}p1Zx**O;I0=5O7yXp;~sBaG2w$J+<&%*+?^{Nj?Yw>B}qLB_5f'
    'X#e$p{-5QRrumm4)L#)N`8JX<GS|sS&d=6<+UC^L6H&YXC#rw>--{!a-FvB_dzenqeV|<(opxRKHtm~oUu_Nj2HQP6G`oi}RRa7J'
    '=}`gOKctC?KLOU1{mGS|$)BvA)Y|oL*nl!Nk`?;NB<mYQ@#DpE-}_Pa87FaHG$^4jGU@o`*1iL_@6g*feSLM$2rP5h`!T;g&F_g{'
    'mF@d^?!SlDf8BcMIrb{{Bmc7-FHHVlB^!zM?9+I5EPahMe!vS`95x9M)&kN}K=y_FuYW!B2W(k>aUt^}5d@zMlxRo@G=_wr$}<g`'
    'JY4v<wq>T!iFqTv?OhrReId(3wqH7v+a>>9ywVJ?yZ*5DPwY~B*G;N_g$Y?V`njYZ_Vc8%uiug0A)mOi#sACyrCqpjMgI8wUAW!u'
    '-_h$0d!kGFK{a~EfA@YLpZ?!J4rhWRIun5G`_N_I{Tw-F(Ae_u9N)M7Ht-3Kmcgcx$!=}Rz01xSx(GYu^}iuvBdO0NJ@?-Z_Sgwm'
    'gFa&$2NIeg=?6cX<?KpBx3oh!Q@7u5TB6#;uLaX_;@+Q%-;TS5!f({|2e5NXcZ4(adE5KA&&M$&NJI4Gla#Y6>BX+J%*;u03GW|J'
    '(Sc`La%eDpZscn_(!;O_$yIX`Q=bnNQOLW~WuMm}tmv#-?bIyxHaK#6;CX(4KKH866Zd%-w=Mk7wxK^urBY?G?DM1O^FoJQoE4Qg'
    'jZ2^V&TkJ3;LuljB2zK*L2Juyak=>Wb3W)I0VYPh#|G!)Sgjp}XsCkoO-!)fx6<~_-owz_%vwjQ7^>(rk!j|j;YVK-O{!zkI&8XN'
    'b@OkXm<fMr=eBzmJvnaC6P%ESGQ4_<t`>uf3H{*O=gflZm=1#F^*`vc;eGenXblP<kF7xqR%G7H(z|_P9lT37rf}@jalno|_~%ZF'
    'k&b_%@Wda>qM~o!W#Sa}<A_~ACj9s6Q{gmKv9RXlMZ}3G#SiSH@WROCJwDy!B@I=(7p@>jASR)ku6<y+QQshkk>zDECA4F#PtYG1'
    'o-z%sek1cBy?{6WJWJ$O5|DrfeCOjZwfVG!<A=6wydC=O?NHw*kiPn6D%${if4@lEAxj8wMgGXN5Lu8hTi&0IYpX4evsb#GDv-m<'
    '^hSr#=NZha-<?S!M(s}aj+|N^kdb|$Rec$u(j14z!7lT5^uq1s$86?z=w^P*I1kmDP%nkPMQ^ghVCEv!a=uFawt3}4Ps1=_8}~<r'
    '9P)7NCUZowM>m4_u*GCGUn2ZGpIJ+z{joEOxsexgn;CP>Bkg%>x<V6H&9XkPyFB&?ee{p4{P$h?@4J<VD|(Y7*R_=c+i-*fr5QN0'
    'f%{NT&xKT-kUo)0O{K012b+Mc3eYMrv55W1+gZ$!=Pty+yeqKEu;3Yax4gu>bQNobJoe5CxyxDV<=$QJe#y@x56vnzKBjI8(!?X('
    '6{!v(av08HBL`-q3dfr>w7(rHJ=v&a)v=Z2*kDQk)+u>uodR|#Lk9jhEP}}Jfeer;njT?Kp+(A1%vd+RYS^e*h6V>34B(1%%7RfI'
    'B0e$J-DzpKE~!x#W9?Mx*1A%At`3zAonleWJPCU^^&TE1Tc)c6`i61J{FT|z#h5B2m7)s}tn@DK?-WOw0E{;%GOcWp4c6IR<T_ID'
    '6%-q|F#aEl9Zc4QH9p(q>z$u(i|OF<dP<%_Cv5)-C}u_ajE0J!Acaw_@NO0QW=9?q{NCJ`?r-i3I1l8|eCvbX3-CJ>p203r@wvED'
    '{05uOcI`($y3uA<@XNy%DT1G0<BsaJIdXSew!{^5DjQEnt0<5Jjuy6Uk-U-SF)ZQ$FZvpmSA|t6$Fi8dzjF-sj*-1TJ{Q{o?Fx3T'
    'z<Ury__kVmf#xple~`NSWoP(2l|Ju2j%T<?(d!9>Vx645Zu{TjEjT4_s1vTC6Rx3ylwZ@L3owvlHut&h6Wx<?FcYU7jJ5XUVK`t-'
    '`LMFsJT05~IJU&m&LY}P6A<KCpsFWttAyj2u5z8P_o;+uqVxCpkoVRB_4tQ(dhfX%zsp?CSV!Fr0{8S!oq8}*aup@d5?_Y-^6u>Q'
    'fN$|Yy-8G3@1#V%ac4&Ao&og-m>y)kVC|wC1{m|zSmh$U<nX%!_sNhaxIgCfT;4@CI0H-V<=F|H$7U+{I#lYlQ%jrCsVv|s2)GK8'
    '13AlJWGT;_H?!^m0WlcE3VC<Iuk4CXF8MuABOfZ>o~NGYkvCQn@^0|o?DD(ee?J+Cyh7e#Uql`-2ZsUY7CAYcO;it+B-!M}<ftr('
    'n8O)7V4ig@FrO;S=L)A1$kWIJ=6U2E^8)h@^Gb36od=V9k&_c!!d)*Z&XG7XFLu2wyc%j!+?0oPpm&}GJ7k9A&<k?#q_FqL=h9lF'
    'zh&O_vUm@CFWBA5Np7N7d~&FUv#<7Ku*Gd|<V61zm&ng4ijHZn;<a*ex|8F7dZY0VpXK;hp)uk^E*{s(SdM)By5SwU`MqGi?4BoP'
    'zR(FUE$0dDlelkUj{BUi&)x5UUi=9wa?hynWJPX5rU2#6Zpf5QD_M4xveWE@p*C9>l5ff|3{pSYWKw(rnYC5k2CWtN9=}WKYWy_p'
    'X1WxW($9wVQYpC{%027+{v7MGKhe?&T&rcw!5|isQ)~8wwCnq0{JMu49htknsqd1*8a~Q&Qf-izt@)RMdEhVipQ{@VCk;+J+R?x~'
    '0<=AtyIIU|n!4!X81Tp+M*E>Z#*z%S1XK`86;1AA+$=S*=TJ#CW+NsrgD*oSw<<L@YuMQ~2E}7354oNxm0`UXx-UJr8$#)EU8*Ds'
    'MuX;CrGR#-f4W+*VvsgXY~&<>$uR_$wb&7gk{)Fm%P`VBrY_qQi>J`kVdE5XqmBt(Di4k(?13gMv42{QP5-<Qaf9qy=_#a!qUM!W'
    ';^is1S{fNum)0hkvPg0Ekh@QWU2i+#ZTac-mdF%cFxBboYz@VS>pKtaOdG;X8=jTUcg8=Zm>C?f3T>ir&^(~Ic6*E1rSv@FbxPlT'
    'e^R<`a)CXpPRGh8qK@@m6Ka|^4MbNOkM*RHKx$i_oBT_jKSibJ&^gVYptQx*evdNtJuPP)QK(XBBpIH#C1l4mIDq_(8FV^`v_0m}'
    'Nw|B?^T$o<Oi<K~w6_z?i(=AR9^74{fQ^U<c1bV-acG*VO7~AGbOTi_2d>*lh41h#Mt+*O=x##nj@v4YS<5$io{W%n&u3{acv{k*'
    'AQ0gO_dIa7lFJK1x^P(T&a9WcsjZr);dI_CVg`RO_~0e|F)0>qS<}SD{F&E_@fejl$*Ydn^Vj3Xu5_Q-47!%?qW@s|SwKO#NQd~S'
    '4)4z4$6eVs3GU_rNF~ESjN4wZvLRa`HaBID&LA95r?>C|ex<@&RB7Qi+t6NVLjkLR*hNdF3zTw2Nc`1?Yj=6XRFrUTSxSh14v@Xw'
    '$0XfShp}OIqXAKbv_I_&;mFRZ;@duegt;24L3C&VrylfDMFes5QU&C;b92~iJ$lQA2%W9mPEU>dd{^1#(vcyqIzL%|t~-22p5@Wn'
    'wafm{?2s;LTkj4(d++m2c9ZhmP3o}E!1$&o>c#~5mVMs&6`uFZ8TJcovwChet0Xt^8NoDsLW9YW&}edC$fg0z0;LnULuSC_7+`8p'
    '@?1(-3S2^0%6xKwsFhDcvv|341|4HO53&2DExvnPbqz`?V0#^gJRMFSqjaKDp;E?@=MotALsXCmR1K7nk<_dwI+PW$dwz}Ws=Iqp'
    '7<}*A?bWZj`bPAwY!p?%dZB`p-Pzo>7;2lx8yqZfK?2AG>ERXB3E_vk!8N$bi0Yw$0PnOoVa)`4n3KrV{#B=b-hhcWI}kbrvcXxY'
    '1j$QxV*Zso@!0Z^`8jG!tF2V9i3<a&JB|&ao0iP~H^@M>k>v-NeqQ+7?r<Y@dE+Nnylkx(?Tw$1M{k#uv``6$kD*VQBwSf%vV|}X'
    'FY)g6n<(sCUcPzZ<;!jMTR+>nzx?vv&qkOI+xPP8%JUZmA`QvD_48|n3t4VKNq-K)6Bt!F9#nZVl^76_$zNSneuwel7LNICA6SL{'
    'B~vne{>8O14t79s>|8+XF&sk?Yj~C8-+{uWai3wXisxOTbOS{mBOAcu8jULvky<ihDuLmD1>lR0MjMAA^`QHpxvC>#LO@}`*qAED'
    'gMe-FMDy!c*cc>q^X716%iBm}r(iO@_YOCGnE~(Q)cNq!%egG{YKB*LAIHBBt5@0Q+kF487Jkk@c=C>drj57+-RIsnpZl>_bhgc>'
    'v5|Eq1Q7aTjhX)+sQaP2G=z+v$>5IQyE{TN2rkza3#Pnv25=@APUHjocSkzDFB}nun47$dkNBp?@utHhzX^L&sD3Pyy!iC{`LVeV'
    'sRa20+c&-amR)<m4jI7lL;}6tlaB8zv!!}2?9&U;6&^m0e;D(mzd@69wH4n|jGE9t;E#CeOMKG~t!x65^&PFhDF!C1MJ<uo5lzR('
    '9%ycTC<qzN$v7|$BD0$)n(S>I@`{o6D~O_9*6=1(#_j23u<su+h1rEgc*gQ5r#t3z6f+s-bG>UmZ=~qsiq7)qaR5yWx?rKFBp}1R'
    'AM{{7kDz0RegJJ8<53?}uN`Ec^Qo%<W6z>1qvyu^!0O3@-nc1EoQ`h-9TL<C&E$SS<KRD@sZB5b)Uk=<!5p1M54bLxAJt`DUsmv-'
    '2T!%&Sz+X%o;y;y?>q8q=jg}@F=u)R7i`aH&0Ea*AF3xtpy2{fZ_xZPT0kxP>fT5PjMVtPmyT<sr~Q$6VxvVNzrjA$t>3QCV|13Z'
    '?HNkb*WOJYZ>}tIbv$5u0?vVSnE}8<BvO3ur8Ph1m|%2IH}GdWyBX7IXrhaQ`-73DXUoG_DH16=AdYsP+y3Q^fyvmnium0v`jnVJ'
    'g+k7S0A9oE;l=ZQtRLL@hLL2d>@sM%w;mO$eJ&&0_C@?3uJ%v2VW?nh84G<Vq89f4A;3M`YHHkG$RoYvh0{}M&djCXy;PBQ%Z<_v'
    'YCG5qrKOuN7aJRk-vV2Yt+uU&F>ltRjgAN8M=$N5cv#||o#p19S@%kXUWwv40g)gx9DiUwXW{&2xXLgT_5Cx#R=@)21|FG=4KbpH'
    'ba<ucRRgZNP1f_6tU(CuAO#TWM9@<eRGXPm6gbt4NM+)f9Hlk!KlDO_Dcuj^ttCMi$051dBJrVU*f|hr6$s)nrM@N>dKKJ+(Ju@L'
    '-?@|iGlBd^)Oq%0dD1b;V&0nuw9+|XNJm#WCN#(B{Y{RMOQRD6J`uiSVEsR)!!m47Dt;BJ*(!)J{WeeXb6+^4C51jq#)2p3#^34p'
    '6anh~XJq>9Ao$-|^yuc;maVbvct9!@ZnuR~4>mEC16R`6{x*kIJom7Q=g!XUAGeqlSURM4-T{4huuIO^4)<Cg3btfMcH{Va^W$5e'
    'r$NF-c+5<`GfY3|J=BV~O!+2jo-8eynXbiZgH7i5`A~fBhvL`hQ8CXcj1e*!1H<eC*esOct1kbg;l&=QTytk|a@*3LMp{RjyW50F'
    'n^H@stoJ4#5Ic|Sn4Kd{BF$4;df$z-_B4*P&*m_tUZjpv^2#tRk#<rT3d&N*{R>7`$9<f%6(YFsKf1k_UEQ0+e4TcveaBGcsX%=~'
    '(J9}#Pe|cc*ejHx-H>O%w0d8y$KYTskJpQpoXJ*y+Wo_XZBh|?l6P|z$tRPaax|}tB8$P4Wnjx#7(`I%-&?dqqWDEn*6p4U&q~Q='
    '{-t}>j&#hQYb)#fnqeJFOR|#4Vyg2u!8n7_*Tk@bMRrxGgr^ZWt18sa5j*7pS~8r~+S$O%JP(OZY_L2ducJLSuQ6cWCs^r_AKvB{'
    'Ziw>1RfH;X$2oP~pRT5plu$@uv<fJ*HWEOT{4U1^7=7mJI1a?MWF(<%<<As55XBe{55$GUWQ-EDM~u?ks=FrkpWk3Pnei|ODLP{%'
    '`cvRDR>2QNu(8aKl#v%Y>y}#|EP>3NPSSq$jDYfT{@lZJSeE0kdIrc!Ix}`*%KXHzi9;y*C)5m}njA?PqbY~m&#?C&{V>c}5sj(;'
    '?a%{3G)|{8i{ylMTs;FVlL+av-M7uyab5=vMn_Yw;=dKTAw^!9=M^7^G9UHFfm!ImoPI}mk7VEDv>fv;yBM%v#it;HS)VJO|C=mD'
    'NF#b&@Y1NFA9gJXS=qRFh8!~$Cfmzs7V;GkHhcb1<dXIJNW4CT9Hp|1X6TsODGNskR?_$_9S+XRXXJtRT|uVPe=npot(PuqxNrDf'
    '<Hax6;wA)h0BNR~r*4{gdUnK+_B{+3!m{}}Xh<k*$)W>>?9mJ;Wce2a3F%=v4ko^djcwwe86gC1DEp(@!L(03N7$kJqJi`dy(3=7'
    '?Fb+b(80U!cxxy#$A6)SA2?MHClVh=FsM6$(-K0hjYuA)8!kqS8F$IS)Ubn_UA}*c18lI22z)LVureI^h~URL-syy~=s*OR0VFh&'
    'Sn_KOr60PQ;B*BhUK`eQ!sqRoraIvTD9{0wH6j1PCsuGoyz>-!R0m6fC>^U!Aa(-S&IE~+gLM#J9O-U(QY(!r2<gY~h9)|3gpHjK'
    'VU6}0OPZJu!(DuXjj+dZJOSMA9y_fKd$m30UW+IgLtESI6Aw-WOK???1G7oo`Y7XZH0P!W6(-t+Z3nhLFYX~+YIl9)Z;B28Ax)Nl'
    'o~Wby*w0GO0{*>4j((LvE;~|r*UgdM>as5;vB`Smzlz?ErIAuJ7IINolv$BV;AmZ_3k@T}m`KIxsg@3sn7e;O9;i&s@b#%1edLi2'
    'MMwZaW`})!9Q<o0n=V*Ov9G0Q<~e*M_q}PmxE)!d88|dc{d*%zP(%r<T$0V1Evz>GrtPN=WIu&bsK(*<1Gz31ZL#9YguUp|YA#u!'
    '&q67}->Jh?2VBV>*}Uwbo0mQ8wTl2NmEN6bJ&;Ir4T8J@xV7hBq+f|>LCuY;pQW>~!#ZJ)ow&!EP+@R(EpA-ew8hG_bvMp<aDv_5'
    'a1i*XMQ_}p2O4rI;p}O9Bk%iXdV?ak_6Q(D*g>{h340@9Z!k`WbjGYK8jIa2X@<UpR4cSj+TzKIZz{uuojTp>-b%+IJ%cl?uT|UT'
    'z;=tD=i2y?y_Z-+Bks>U0t4}JZPhW<WN5p<p*xhJJP9q6zO&X9^#QbsNEQJ8<qKC^*jR0;zP8{_TZx^B5pkOL4dwMr#jco*ow^}B'
    'B2(7{;(?6haN8*Sg`YuN#t7CS>0om*46F##?k;In%~p$5nVc@PSd;$habY?%Yl{m<FTiQ%dD^}D2jnf*@GN*(prPA9HY1<W!V9b5'
    '!MWrSgT4&IpZ13|-sA0aiY(xuog+Th2lgn|LG0dY!TnISff)iK=*on(@_6srRA6RQFa1%go5EiI$n?YE0mchA<0avF;WjUga_`cH'
    '{q3T)pbda<S#PopSK91%GY4ewcEs^L;#$Z};C1O;5J25$^fnp4S@wtph-KJR;Q1QP<Q1&02aMqm(5E3Ni{p1>$SsigL*MKhMOH_u'
    '@sUPJ1BrhRwaw%35t)b(>b_l<udAu5UXJi%Z$}q*BBS+>3r5{emRWz<Bh&O=hLrK)2U2Gp*zYnGfD-~RolNVH*&88Nhq9-?1QN>;'
    '9<J{NQRbkV?|Jiv505>sm%Mj%JooLU=Wdk`q{YiNhzyO+JM<(Q<Qb+k%AQfZ@hJMC+8&Sr-a-F5jPyZ)L>k}0at*eY4EPLFczwJ8'
    'b-(g>;Ygjy<wA{=#3#`a5GKE|BEBv_O*96+S+&Yas@7TUvM>n@Mwo;GrC(!*(?H<}B`6pA2n&Fxo?g!LZfF@8?1>N+0EM=K(A}Wi'
    'fYYcZ{JyG`<!ZmqfK~wm$?+b=5ozGC5HK!=`Da4}+FvD)L15-I0BV!?RfZjskmYS3g5*>f?u~>0<y@H;)8P*Ouxez$V`n}IPmtWF'
    '(YS!{;sdrYU>_>3fqN3%Zgfvx>z_GQJzwdby8p46gzRpd_~w~|sk4horPiUx3*YS9zs(!COuxlkeZU}+&ut+ChOW{*zqKi$vzt){'
    'isFS?4d6}|S782JnTJCTKBtX8RwF(PG78HM48%`jD@f!KMm*dPcg-u2T0}KWpLaJ0oc`~yU^#TbGPLlmK4dSM@R<q6?QIQxhMW`p'
    'cViZD#u-ef7Kv1Tu=E3{0-)d&LA+DnCp!;OX-|gzS-Ht6L1yZ)OFMH{<%V#B8fCJ=oL1*^R?^GTZTj&Cj6~W&0Y?i_UY~)jwR!1l'
    'N9CP2s}7bI<k1zutI0gWIOyCD<fAEfWRqobCv&m{oz`+9YS8_9DJ`6q%4yTJb+e0}=9Y$$mX`XFj&%)bH!O;k(;!j|Oqa+)^Z{G='
    'AopcPEshq4c$iT2cgUcm%WTc^61Tf3?uYls=Mf$<ss{wBvclg!Xg-72P_nyt+~9=dt~`RE&wF!z-VXF#)8hk@;LGfB32+T^MEJXa'
    '+pP*@p|_WiuV<cBjZ}G^k%BWx64sQrXeZgd8hS~V!i4naVJjby4jsa#$RK5`wI_y?MUo^u(y|V~`sq^6C?q@}Vh^Z1_}+peoKXr8'
    't6&j(>`ha$lQs0kPqXg*^D)blldFqX9p(%A@_hllOVgI-6xjD03CU7yl9XvL8u*UQ<1ABgd=~I`^Lf}yH0T3P+kvkBVI1wdEMx2n'
    'xxX~$&3&Ms0A=3Jo&Krx^JiG*mrdxYjy%_n1$fz}Fpr$KEoq#>FO1aCy1Hc^G4CoxMr*c{oKD3BI-SnLaKLVTH;&&=+;>48+LP%='
    '=-)@`eMvNw@UyUNldN~oG%3ceGmA=<yreoQDXBu1Q-mxh8)??FSS~W_HMDHuD@6egk_omLh0oUuzB1H^Q%Xj`mf8ksQXzc}gwG=='
    'B86ghce-@-B_$@w(ga@e)WYj{$@TTA>eiW<43cdNQOLr`Xb9j$J{Q{)D3obv)AEmMO|2E<WX`<R!mNE;{ALSdG4jqR7BESFbjO7u'
    'Ss#*4A#C!-$K<#k<tpv_DU~R#0mu!@{D_F4BwNkc&3*dXh>$7uLdtSeqN8vM)tX{$Rt^gCU8jCngy&F&C~eV)r)3|`NQxuPaV_T?'
    '?j9Su!@BU45oxN@%ajA};U*cmh22%~aJWVf<)q()p-*e<vk5@_rVB>8#&;HpGwmFmNuy33_)zC6Hot=0Cv0rRt+lYQl`?H{RU56G'
    'm$Z6<0vQ&lB~0)if({D<D-?&7fp#Y5o?Qh#M+4y@EnLy`Ja*Ibs8E4BAJMHbPGD1B^#{XxGb-?jP=SlaY+d5ERz@xG5*2vJ%Z^=M'
    'cDybxn}82r0Ri~Xv5mWS_ZISOWmC=<qx}vji{5>{M<y;#es&@Kl0JXvF1H446V><1ATzRWyZ`8)=ifhR`wh{j9?$8<sy(0-HF(wq'
    '7XZ)#v;hx5Y5@T9F^^8?1@jIO+hkhZW7$6qr;Kp!KprJ_xUS0=25eW4ktcGWbsiGt!yz!jN&~PCFxMxm_k>aAyQ#{DO~8C@_1<UW'
    '<B&<@l_m%Gq#~m`WqE1V`Urng11=_atF0CaoA{X*C^JLVwcS3c_&j{5OcY09;$+ZDzt}xDyM7Gvd1`zTQj}p)zu815n%El`Zt<8i'
    'P|4<orTD@1)=BpG2P8rVF)@VEI2qa-V|!_t9kso=vY(efU)@63>649qz{wgKlJ<w;m!lD9q%)VR+No=|<$B$)uU7{BSrNWpUbWBI'
    '|8Lvu=l#wE>OHkxzw}Fxn*rg~9&k%L3@7@Rgz=i7(UaL`g_VEAxfH=#mC1s{1shDluw^zAcYT~uOxlF;tgJM%@qSim$P#_li2rGs'
    '70b>g8NrDSD5POa>>(ApVL<oOD@_H^{9o(9U#h)Uhg_#iHix(BFoFPk?J)EtnS2NgEW@547+bc_yTWK(!G9fl{ju-$$NTr<$@jq8'
    '(QGyQ3gYWM-(UMG1oTw^1BmV+*!@#Hhm9dddjyBAc7{bJ$VxDtholVTV4Nnx9H-EQkAoX8?6-gvrcKW{R8!U(XDdB#7?<QOs80d('
    'O!xf@d<QAUkDz`NJ`4#xebVSjdAJm!@=!BFQq^mVR;5)5@K1C&mIq3LEqYq?q|*<*mJa=|GCQz6dG9~llZ3q=yGXQmCHX&~Yu0dQ'
    'S{yVz9lM8`BZ2S}(hZT`vM0m!o~&#h*#Z0pvVR>x>k-rzt;pdsn@VQ)k`MYssI}TXtK`^JG`7AxADH`L<!Mqh)`NF0gpj*naarl5'
    'p2Da>m=?f@CIhR%43mGv3s&_oDtHv@d8DPQj`K5?^qzm{E8#I*eKWD&an!Sad+7(ACVYz>FyQaQh-4hoJXxakoXBtT@qLn$FOc$}'
    '0R3s~il}>sT9Dk-b)acLcJ^nU`(%8qlO4)rjZ(lSCG&ko8WtNtCT|K1zv&MU{V}<>`vBC3feif{j-}&z*wp5lT1T6^Elx85O$e}$'
    'XH_gUI4(G~jYaucmB=F_AQ{8=8*?grf+haLZ5GJr(=#zJeV3`Aanl^mMygpL_Bfcgn;+T!iDUf7*uMv3Gv4=HcduFLwP9KgHwt}='
    'e|tuv66>;?)gcd#6S5qU)|?|dxF~3jjedL=ecRQOKVC7Dh;3G#vLU&&uh^H$jzRBPzRuPi_%zm>B*p7l&B@;rQsSYzOLw2a4UZ2M'
    'KA;XGhW(#B<ZqQ?1!VFTIpEAX49M-ed-2_qR=GySF(t@j%0I56cVu4c$`C-C0|=u4C#>#AdKS7mVI~l&OtUr_KrfPj?FrBx@Pdn7'
    'pE4|f!J(v`xKn@EZerwn?nPev`toHMQJf)v%)J+6-o0u#k3*=J<~(s8hBp*?l}!C8`YQ<YiLv{W`GnOVX_E=oyVhYi@hA)@JQ+?5'
    'rZtjB<xgyT;+1i&Tlzhb#%xD4Oe1<Vkh(NfK+03J8xeb(7>Y3m3=3#VRBRY<>zjmMky>>5#cOg1@=k&1^`|an>Tbs34fNYg3hNBr'
    'M`>r~Abd2X%-EruNP!cOOeOyZX{H-ON)9Ul$XwgNPP4-bvnDCr-dsnDghV;7B)S7wdQIuzdxA2P7k3aYET+xQif}SnKXesIvj?2F'
    'uDf>4$x8|`f5NbuN^sx~#Oc85B&QbKP7V*)&xM^UFiM@n4ZaT=7@HcSQ;~zZBEB%k`@nrY<w>>!+r{mKc9RR(w|Uz-^=%90Q*o<w'
    'Kbx@Sx^mAQ>LNvF86bfjBLB78{8}wvu}j}s%qN<YPE06}#vyYv@F`1IiQ~6Dg-J`wlvv~=kmz>KPzvZg5A$i{c}Q4>Bb@_@xFb6o'
    'iZ6{aT~E#&zs+&uP9Mj=53e!b*LkI5^*Vo>=aMTAp^qHsJ>TPlZasDlyf&M^H}xqPb@AFj?Dtr!BWUV^mL)ups~l9b33i1u<)a;s'
    'Xn9=NQBTuqxx_dxaNiuw^TI7!PICf|p(qLa{Uv?+6eBa!wiS&;2cm#&4x-INR|2A-tPo&57^84L2uyRoiBN9_*zK5y`FLuxZSHx7'
    '{AuJD&Qs@g<U?CC=g418c?9PKCv$Qvn&?x8vBbQXyl&-b<Pq}>*CBr_IzLyPC!|w#MAl0Ya}toPb8m7db8=6L_?`fzhygZnafDjQ'
    '(jpIfKMo|B=5`Qsn+<j5zul8>{SBW>?TBJO9LEhXeG0U%{?S!_Sc&SA;D_@Sp4JIjo^sBv$~pV_yuf$O*o2_RraWtGBrNEsADg9P'
    '6X}LC2Q?&{apt}MSnU(X*BH~ya|#O+6CC5EIKE18ygWL|`xkV10uk-0i)i^Q8Sr?);>$FYQ$8((VlpTX>-?lK6PrG$NC0#zpFs*4'
    'i#p<XKH{(wl;Qnj1#D=Os-yTPO35wi-T2Fw<z1+iWnM^VUpZVluXzxAlDiZOCkA1wS|nfv2FsW&1yXNh3_?T!H%yp<NaLwWsjNt6'
    '0ZC>Ds(=$Jz=Q(f)s?)P-2|IApWGgM0Q1g1w7d+zUe2S+FPm+K{Hb=CV1JcM9#q~9d}Ka$*9g1nMox}ZcHtCK6(rUHV2`_wf&+sW'
    'hn@BmEa<w>X&542UPTC+%p{NlF9#c4t<e9@G}`DMr4l3Z3kZRflzCl$ffug!KVNXtfh1@;wa!yg2)H3Fyz7g>h!s~ZDCmwg?F1XP'
    'A>;IdKwp!e+_U~^s52*&(seTwisv>z^fo_WP%RSEt<yK7_1DfShgA<xu2A4+(~otbALjfG-b`6L)hm-g{Lw2<!)+(Muxj&!o&vTk'
    'eVg!UtAj*S0`KS~u%8jmjiFZP+f#F<lI>J@D&){L&x#-vbdi1ayhs5-vP|;v1f13iF*t%%kWKga_Mvl^ZS8Yma5Q)ks@5A4a@p)v'
    '>f0*&HnF<0$i6)-`9*CYPbl=49jf=9zXt1s2(8IjljFvqL9tL9!K?vN_ytl+X4fy<!&j*BY$jaShVXGqt+WO=+adTzXRrlFzHp_>'
    'Mnfahv4xM#yF}45#onPyM7qrd@m#^OV<`%CE%&p>Q~P;MC5+1lI(-43S@ZBl=Tw>*b{U2@qtmdsA%xUY*VfZ6`0`ruzL4rQhq2Th'
    '#*%Uv>#q@;b5LXtFzxFzToK4=>;O(<hi<~m*6f)+11VBi-wQZ;Zym?b#LKgZ*R{`0>-v{CkwuC=FI?fmmLpjdz8UFdt@t_vfA((m'
    '!(G$K&z}2yli$VlcX8JTb@RU)6X9Dtat=-0p7k8?hZx__^zn-s6ol)caxz1?QUIN01P7UM?v7j<&I>I<^`K`lL+NtR_jxXjzyZ26'
    'LMV(<h5Pj&2BU-_7JbIJ>CLxo=%GWZFk2&+TqU1cEEOzyF109W=zP)d451I8{m4k5D-SxX4X%9HadaOW>A<U<c@^iIl+-13XWJ3H'
    'c%`@H?a)ahAuo-D!jelG+*5-lNGl+iI5{1QlwH{7{X-LD5iQ2$B^^ym@CI+(+;r;6k&V;Rpco_AQB{k#fSQNy)V9&+87(sQz>}BK'
    'P3ca|ZfT{l>EJdaT3CaJK<eCYu*=r48-Bp)v=Q$`#!HcYYcXxQo-J>)^6FaLhTPtc*v8|>&|MWW$I}TS=(>m}rxD%nL+_g`*QQt!'
    'GE`R9E^xN3_<s2A)Gv#B$9z8^R-9w$+4sh;LQ~ltPPps!E%G%G^xYhgMl%u|nC4fN|Lqx_7KrG`89&&e!5Z1aV_F>^XOpCPwb-Cx'
    'Iw<BGmeMOXIU@`ud3zw4BH@VvSwS8<ZsgVAkl}q0(rLUsh0hpBi5N9K)`*6P=-dnWI48#8kTUR!pkHxYKz7>Wp*A=Q*aKpqZdlnc'
    'CpI^nDZPU0wet?w7^C5SH(cQd;KAty9E)+on+y*(U*+0=&->NdCGSKoc@KCHL}M0*dLIbTY>lH3k<a8O+`)x?i_{N!GKN9H6YjoX'
    '^ppor2S!jL54hpU+?%}ZpooVvp39W<krZ_o7N;rd9)_}b(b$*d&_7R=jJC2dW~nkSU~rHDwQ~#I^L8F7ANSSI5zkls_6Y4vIE6g+'
    'S7v4G1B#e=5*B@aB}@B4N9fY=f+xK48>zJX9A<;;3bw`z?md4JPKXJ|I05&;YRuQkYeiY#BluHPnHw6&h^$#0VA3-_`uBWa{anhi'
    'J(vDELwjM5OE|_wt$o~c8h0u-i%kQAO4>{GQ>bWo0pv2$p0FoRjuoeJO_ffK6wS#-X<Y<up-r-f8)TQtzPDaxgvWWIrOb)6G9s-~'
    'a%@xS3bK`M{q`+Va@such>qhNouO$)tY$3F+!6p|8O)`!qRuvVbsTMJ7l;NgwJHEOVe-gkU6M*Vm=W`eN{BK_rYnI0Mvs|8GfGf9'
    'iDa2%2rWq|j&HIXK)ju&*`(1@XTWHF=`Qe^IXR^E^GE1`*`yz+H6L60gW~Lb!w)&E9=pS8=s_TlC&F+DA^^yohI$2)fn03UXPZVv'
    'vxFC65$Zin_WxS3LZ`Qy{4|-zB+p>qM#LjP4)*QLIu*$C4V%xhwA-(6zY-|dM2ohmTAg5-Bny@~;MozkjWPM<!Snq-Bl;nDKXY)S'
    '%TA3hyhqgK98tH|cg=$%Uj~%Gorj|w*xA-1SbCth%W_7xGGTuXH0qy%GPwyS+&B~UA@yH|zAM;oUlt+%A=@cFunj4*dU*${Cyy<1'
    '?F3jm&t++s#}>g_PWFkO<ryG<IyxD6PQ0gNfI0(#Yv7AGp5YqID1Y*=L7T~WTFiILC<5nKpT3YI&LgxJv<>Msj(X&(eV$_Zk{3gp'
    'OWj!&FheGPqm_N#o22N-t+e`lXeT{+p72`=+ZVWGj^fn`^#p^95f-Yz0*>8UH8Lg)rV^)x*p$9Ck+XO2;m|>7y9M<wfFeHnY(^oL'
    'a8<8x%&JbJ_9S6jA$umn=1Z>R2{7Ug5iD6G&+#d9O^4hfe}q{RK#Ut`>>RtMKj8a4bPPOs{2!lWL;}ONA&{?w;K|g%k`9;vEe?4s'
    'f$}l)P}PVzV9-JCP2di1t<@3Ej1P$2#XZ7%T?*s95_DY{?9{SUM5%MR1^jN>3S5@DEkv_xt-~_qY4}5_QXWE_C`y$}3F!1Ffr5ZR'
    '7#1ZbOSqJSE|JUpG`<NA+B9y!Qxz5n2uYb3AL1{T<KoB#k#gl-fWM=_FeOr+;7pPDYysmy^Q?zo2JPxk%zFizw~pqmoUif9e4T8<'
    'd7h$L*qeUP`M`Zu{ZY*P%vNus@<4T`a=OiO`ipL6Q5%R;rKA4=F)j}WfNkCismA^o*7jM!H!^U%G`q~g2vO+V>VWROk`e$w>?YC8'
    'SpD2g)<3Y~Y@t9~E7YErIeRE3l?M=<bB@ln<29#z1oUuqOY&CP@n7Ttq%8rqF`dicA^MpJGBBJ0FFkT8^nR%#vQoB$-?nSm6-3DW'
    'jU3w+>G$UT*)8r5956T<4#^JWaU+Mndla^!o`CYKpTi<s1~M2Dz+evwn<1#YR6rpE3UsTmTNExN%XkOMU&@?rG5CeuvkuTMDM^hh'
    '1zK7K`*FAt{w5)G>-m$Nh>Ue}9u-$<e&BrBlIYzS_q{pIBmKeWVmqdJQjKmSYdvR@U<(oYrOh8)R~wAfIxmV&@6WaV^mhJ&=iKo='
    '1n6+WemT8!zr1(<?8^}}0@hJSy4Uo^8Bb9onZWhR2k<nc@Ezb?(3`TG-i*WF-h3E&_$e1$Rje3!9oi|Bd)_XrD8#rd!9mc8VXWEc'
    'O@R4RNcsAyN>%C~?<{@l))UCZ10J&<xL-fvhrlneUG1zD066$_QnMVprBt!PjUXI>Sv(?z8^5QxFE4t%E_b6q+!pSd(p?;UR!HB9'
    '$E*TubD`b1n7rCNEvexX?0Sjv>X@?>?Ft*axu19Or1HQ~czM*tY;<o=jo&Z7fA{Rr9SP@4!re2$(QjS4o)lo})}@Lr?N80WWh$k}'
    'rKd60T~q<3I+eP3Vw4J%DwYBmdg)Sul3$ci2DDL%2}{mxl@Kaq-c>47cP=F=<wdD1N_ABN33Tf@D&?t^c@4|eJeR_daQD)ggkeup'
    '$%zu}K5<bBi<0O4YE_E5gwQ0=uf0<@Pf<mf4JvM?a6W_wL_gS5+nNF<5Jg&<&%JrS-@@b&=@oD`*e=`N)hVh-!OGCN6SN5mxluYH'
    '>GS64DXUX>nCR@j4}L$Y``teElsD#zziZ~t@$gFXC*GJp{)?DDEa%HYi8EV2&`<>fnT7l9A4@(&%)k1X&p#5U7R3h<U-WFg1pHP0'
    'girAcDNtksHEC%W*X`{RIxsC57K>Ioqr;n%Relv>?PLx|ih&E&h%2Xw0#+d-KS55gW(&(pYbPf$C52l3dy7+jgz?*(zqTFjr_K?='
    'W}u`1e;>e<YI$1zyz`YL&J(@LMtUePNhS3$``-6gVtKiUtu2YQ$GUD?az(!>Op@Iy&!CsF`Ix7e;}P%?)*k{B5<p=!`Wl<B^fv^r'
    'gA749!-7Idx-2D!`1NyXfMAJIKwzw7O94wQP}ca9F69Ao-@|B)$Jmm?09%96k42OU91Rww&`YsDt8yu;Qk5l-B{t92rDRL4$~fsp'
    'EE|pA@N8d#8%cF|;6=|;$j`6=oR>z4l9F%uS=o6}SHPCY<Ttio&dXZW26)~6O0OG)Ir_6fz;Pjtj=^J36-s)mus4c&Ys6_3zLR1;'
    '8io9(B0ep1tI&MioM4H}&bBt}+sL)()rwpry^sRV+mh5q^WIe}a&J8)ZarnM4+cvjoR!c7c9|xE7TD5Xg!$B*n>D%>c~}^Ryk@@j'
    'TsBlN`kfnKZjvMN+&|sob_DeFdO!lxhh6z+!r9ygW7atVIa!IGqxm`?<Qy{+%uo!la|aAOxsctqX$+GkL|R!w*ac*k=lo}DmvZ+y'
    '3d?mwr!&%{uKI<2o`%u&g`?lw57Wj}41F#32%=A#{_5c!#A_Z7R@N_bCxghqREu?_4>-Z(alL>%Y@nD2VSpqJ$7sLOhk6z+jed+('
    'm}}Ji`EwT@L0`%Kz?1r`=rgm)pQ!uFH4Q;bVb{FCJkdPyFi*m2e%v!pPRn)VX`xP_`^B8t!4pP<@RwV}BqHBefj^txW6Xb82bm1x'
    'w)P{NYYmTR@12J4aj}kq6g1t+vx!4s7_jwBn!^|9Fb4ML@z(6g=JwCZ2{LS&FHwtNEdRn9TR%AsE%U<p`2AU#(=7Pix>WP$DEaF^'
    '29{g=O;#R{)`7s)nUAsa<-DhV;+ih7gF;~;XqnFo+wXzx?h%}q2FPH;h8CV_!?aQ77-uHBu;TA*5EThuE!^J;3ay9YbRT=hU}(M5'
    '&P|8zd+a_y#{pY3`5BUEcDndT4rQt1cctM>$xf8!=TRWY5I9Q_eii@#BazY`K$z)aNcRY6;{x;rKd<ngKu~)CuR}j9ZU@AU6wL}_'
    'lCZ%0L3kR(cssdQYvI?)NxY40k307v3_xM^x#ynW<Un@)okyhh^<=RVX8GS8lkHpP*}cDC@@zLfJK=}C5-m<pWb=lO%~#kn;upwk'
    '@iI@3(jdx<GglA-w2=8s78BEND7R>G0P!NrJt`gE(w5=&QyJWtr!w02_A&ybHn{2l3_+lBk1`KpFeqn;z>@~JH5d$IdBD4^$_?Ue'
    'RStPwZsD*p;1S7kWs2@9pFVsM47V_24Otq3evJhs-F@&l1Oh;QZ{{~5B3MFQ`l$MW8?<TY>Z_JV2mze-81M_ti5ATTb3)V`%Mmdj'
    'fT1;>dbb(b-Tg$-ya2UMil&BX)Xc+d?$P7Dd?7QY`CuHWUzCjB=61i05~E>}iwF@mAMNNo!1Amscry8Zbar(pLmvovlgvQ~9q@3I'
    '7oOsLMi^j@v3tMWElLdX%)ZE9Ai+>pMEA%XzM=3=<WjY;c9D@Y^~XTit&rm0=r&oP^dY%v@6cTtPY83DRfH2n{fy!>MG${pfUadk'
    'a`_yN)Z!Qc7NIbX8p+ST&k6cO1Z;8gnXBj6=rH$wR`*%<8~#LuoIe<}Kh&Ii(45aGcP~%3a4D~2?<x2WfxuT8<y@umS+wQ-Dq&!S'
    '?)(I3mf6BZD=_BHN_Fyg+I*+UA$Y_4$t`?+Mf^+o-xwP4R~^OI#(x#Siikc4dhCTA7mGnBL@2$P8@IP9w^||EB(o9nfl<epju61x'
    '5AU+vor$}s?y<}9ns%-ZuP3n09b8TX+r|jW!=W~XAUL&~Aj-Vozk6`^yA0IzJS;j$3iT_Duar7sRvJ<$v{!mg9`2;@FMS^8`wub$'
    '8Sw$JoF4{e^h-|@TS$o~^f&Awqdwf<LHGUl*7s+`#Yl*YGMrnKP#oG8Xn}BOB!rR&mbuqP-$6@Qga#8NG=*Jyb?#SP;Ah8<A*l%v'
    'dr|Csk8JyR>Lwr^z}<SRyjl)WEoA}ekxZTeswJ!NhcEqb7)5#i)$^s~?g_>@k*YCCBt{uREi!Em98=62Wa>mP56LMYil9&#uct+V'
    'K(v?@mF}EHJTh{E0E@XG@EFa=YxVVO=CuMcQ77WsN|db**CU_%yUs=;_k4=*)3qa?XKPAfO?4(K4?1x(KI2R&oHIrxB4Q0w27{(2'
    '!E7|xN+np$eYy2P6-RM<l(&I~t?<=gj#ff%4n0Iv5P_8ubF>Js_Kay%{^cg!1rD+W5BFv%p*1EP-vsX~(He!4Ca!#(3&_xm)=g~L'
    'JQN91V5~lcE@X|?$f%9dMqsiQj<$UX_+zk;6*;b%2xLT3Mm2vD%XkRAQPP#uo9-xqc9eSWj`I2Bgy#5wXHY<szZ1>TztS#w?L&x;'
    '4+GILc0|WWK;d3M6wRrZ@gO!?zWkY|k#T7aIxUg@C@`)G*OAC)dh2Cj7#+5y)T+G#agJ#jAwHwp4X)rhD)FFTh|dHau52PX$M)Fe'
    'AoXp8^Z0-urw_!Sewq)Mzv3qXe{nhB6V@X#gU6$S<pyaYntl#U&FY!KRJetbjM*|`7*<zBAI6`uGT}a+aSJ}H{uCIc&_7RKEb0HD'
    'eNV+ohMASLjxHLeX2CkYq>XFVd5!lc+DGPJ$O<#$_m9l`28HK|z|8p>hs68|4~eB38tT$3&~n0q+~}`i5T5}L^2<6}J<6kD$Ax_P'
    'Q4?_?IhrjaEglEe04I)tYTW6Dh;%NZpk{HrcB`Pfuay!yqzrY;G{EEfDiR$s1%(lrTvq6iVMd3HGSqpjLgY?h3O%AZAa}(rFogw1'
    'Bt$6-6s7D=MMB(&=qghub(b$olM`_vDGegp7>fF`K#C-!(KAFt|9p0mxO3$_L4H<{fI%ZhN+jZk;h}Tg<163r_}cLFisZ?oJ-q_u'
    'XXSY#4TzQ9z-&le7M?zc9C>tz#_j0+$WLog%BqxxQ!)5%txG);)3CD(6&=Px;Zo#M89qI|G@?4G(hx2*FRmeOh#5sIT&h!vOn<JI'
    '2t!f?r5HUTN89l4Mfg1N$e|C`qcv@;dwlPt<%u@^jLPSV&nfKcqy*v#+@lilkUz1Q(~B9sp2->$IvS^D=m$HKo$^KF8GI(F!nB^b'
    'bz|n18#~_8qr%*70kN8tInBXfN>XT{K+&B+1-F$ZhK;NfvZPU;dZqT1f0TC_lle-D$dbVc;4W~4s>&lj82h3)J1S(bxQ9rJsMJNJ'
    'EJkrhKuJ)i*c@e=+Cw1%NY@5k_9TqcIs8WC0#Gu7E<)v_voTUR0ZdBOaR7&fWFZCe22f*#XIE_ly7BQ~D;l<d9;fG32IJx=3S-i2'
    '=)6=OkvxOqgYyl*NjAbFpvf~D5in<c+ys6r#?wf-VCNp!vL6qm-%?$2_OGX4DNDOMp?geSOO6_I1#z(gfD0_uEgAssH#g?feyEfJ'
    'a~S6f!*GzNtIqe$gRpzP==+;_hwX{C088r(#X`W71YDYUy<Gv8UF0jB@t%BEE?v)``y65XmUrg_Kq(<T-nV}~RX^>@35fCl^e7z6'
    'N#6<fDDR<11M{SJT6z{eiV#v}Z$3_sMZtS>P9E(E^6Y}ZAX!ByokU6uf=z&w=v5KWtD@pdy?05e-JV_gRIQ&%1WkEDQ^FJX@F)Hd'
    'Jmm}!^p<Ls_sbz%tFJG2&-^{LYX=^~2xLUE=OiidqJ$APFa~_3!0wg3nH`-vJRS1_9rU6oB_|zOZ7DBGMS(WzQeho5wJK3dQ=ry+'
    'Q6hPeEG6oVOu&O&TCEZ=>i+%pzV<Hr#wW<{+OG*Z^Ncg_jQx`wo)lIk*uqq)$kLQlQSzeHO{Y89<7TO&;?&JjkL>}aI+X&TvYHb3'
    '@cBgvMF<<EnCFsnTO|U~oOi-Rvz1GEQ7Vg4U6s<Jl+k!al*phZ)~QrO56q-XUX-3lx{_JWf~B}9g*un~qU2VkxF`i(A~?+>@@7ZN'
    'n+asLIFmC*qhUkUDB!5G2nQKS^MKm<DS<y20`=OZjfZ>j@FLqR-b3QbRT)dR7~;--<wdA;_LTf13(dYM!AKjDj7fsAb<#{XPKfe8'
    'S0oH`NQ<{TF?`p|%HdA*>a)^)H7n_0#3B~~@+g^@C?JEXG0hYHkAi>r<7dn1)NI@%Pq{kF@1EVoAhS(DZ>$WnsCG{6wer6><d}c5'
    'A*XZJnNWHy#wjoZnbmuoFvk`9t$jEpkerfpDdX8>0=8r+SPoYI5mqdJbY$EYRDhwy@wk}B7z>N<E#y!U#&d7}R;J*eIwxpQ$t@i}'
    'sodcGOQ>}TQz--042D)Ffw83yWl`YMum{eGcBt=<wcF7RLyuAv2D)K~aD-@B9Lpdr@<Nc1TJg<hDBeWk@>8@chLKb`K06v%Nsbz3'
    ';U%9aPkZ1d>lDpQs`e0W^oYd&c!0&4CUxfa$Eh;P))>u2%D_#zpdV3T6iHc*t8!^&Po|@w2JU54-d`yfE=Pfw-|mPIo15j#<*Le#'
    '*_SNjq_Uhg%Tb6<qJa74G5S;9fI{DZ!cddr=4O4AtnzNDtP8BHo9t`z3WD%Tggm!ITx0M0F^8XMPM2%zuNV_CZRW+sCW%CGf2KB^'
    'Gpuo5!?Ve+UAz1p5ur{)zw#PAo3;6LFZ649=MCr27aQ_cM8S2Q4A`NO-CIms3)#B-dbsuV>&T07>+6znxt$ZD=_Jba8ac#Y@um{<'
    'L_-H}g}{ERPuhIGV3Zk;qlotjmZ6(XXZ=dhNYHIw&+l08%Re_s_%j5Jhh_gT;;Rl(y8w#mdm6}$QBHi?eIoZa7g}B|<Bj!b|GY#z'
    '-R~Vph^Ny!<NjGA$!SDcH$o%#1Ix|+P!rP5?*-DSgj^NaZ_<`Q8$5|TJ6LZRD(FT`g*wGl$O`#%vCbyDwQS&ivVqji3j-tMAuVrd'
    '4IyWw!#SJ@o^QcSc2E9%?8cE35~_r9M}fs%iuL`my7CJ7v`+LN1OO?_Smjsp#Peqyu$^Dcn`lGARLN)R`Ey#UCi%#ewxEU8zBX{r'
    '+QlSsk~cw$BC<t8jq+%bQ0;nvb+R&r<PY;_mQN%8Y~Ig`+0QmyLE<7Lz<plN210tvK5_%HeP0aVxD~>CD}T|pM+m9Y{8<3CxfQZI'
    'A%L>`U6G+T);Xw~Mr^^A_p!A<p?NA0QUUmAJ1mHtX9d1@BM|A@9*vPw7yH>wBw4ku6@w7Gja)y6IO*@<XV)O@8ubV|dj)Ont^|j#'
    'W0eq&NLh`qF#(uDR54n?t0Ja)ftboa@2E3j`sw{Rl<jh6i{xK2fN5R!yVp`AmiZG1uJW}JRBbDvH$<SZ<W@c51deRPaP6rBtD-6D'
    'tD&g&#nK>DJJQ*QfLp_r^rg=gNUINhrkq{@pXiQ>`YrSP@EXs5)=aNgXL?6nMM$$_kXnwIcps|Ff_f1N!;3uuk=Od9%3K~V)e%zh'
    'mc3kM`Ceq!?$Zxwtix8RJ*zvA4b;^Rxi$!V!(;6dzg`~S>+cdu7`soy_s>us==RHUi-Wo-H#B=J2U*Tsj;;6cl@phNbRz<*lYm|*'
    '6%=Zb(Fq5Mz&bXf)Hb5y@gDH8pamV*;9@`v8^OmkT;(UWgW6>S<EcF%g7F+738TMy;KPG5EF-@GWj`^{o;3*ffTRf|)|u7b$191j'
    'm4JAf`;f*d=1(H!c-hXkIKn7Zl8bzCE@6Se0Ym_C3v+CPSIgRVe;~5XXIc~P#K6j{xSj&CcB6xC<<@+0D}QlpnP<pGzQL%O1JvY!'
    'm+*CPOQI_#m0&$0MVv^tOgA6$=^sVduL%g<rEu&hi^GE~B=Kv;$aD%FGYOCwXHxmoITbg1we<QE=N8KL>l=yNL0>8+=$BXhHbNT2'
    '>o>l$Rdf2fUFJ7Nb8AdP**z(o?ly~Md+b=Y4{wEK`*K9v^m0VoBOD<vg@HH*nnD!x38(^ab!(hlcRjlfS0tS*J(6<cff*&bZ81o<'
    '8$37>AO%NgQn(NBXcE^JgHALf3}aBqR#wW2ilQxx5;7^M2)Sg}OZbbz`$(K@wrDRMTtpzer$A^=7=ntU_@dq&wdkP(ObjL=lLvl^'
    'Xq%J*f!q-^18S#-H3rM>SZl^|1~$nejv@udeyGBpl2LL8uHCt5A}{HO6_VU@@^Gi-@3o%$T(n%@Pow_z(Q*}HZbEPB)V-<i@1*A-'
    '=Dywi6>{#=U;X$;KlqEE91aMc3jyQ1mCpzl$MLXeWfAvEM+1mCjF>2qN{C~U7p27dp=Bv@oP(+Z0<;zLh-aS?@Mw?%A%qZq3fwQ;'
    'EJZA($kKc&J<*aq(~_n2UL3E6zIG9sH;nMi$IG^N;TX=NI|*a77_d=R<gx}$Tob|^F2y%3VaGz)6;MG{E+tbc?7HZUw}&Z3GT7%*'
    'c=b}bQi|l40#-d-LcgLYT_-Zfy@F}>h|8deSu4m#W_Sblas2xr<husEwX0=&U;tlXB2^JMxI&zQ8%l_<JD)%nk_MNM*dAfPyE}6C'
    'G;ZkGso)}o56_5I96A|=m5>-5DU&63GA7ynrWtn9_QO(g{<@{0Ehx2BWmm)1M6@kAP>~?^tp|cJl~BsEE``@BC0kNSrc$By0lGiT'
    'b&`;XBR3j0B~<kk<T4M;5f^s;aNYUC!G@yDIY<qX1F6Le%z61K5~3n;UKvh{^ZZKlKMj)Q^N_7Yp8w%WU_cR62eFq2NYAm$w~h!7'
    '76om$&K*teN+-xjXD)%m%Gh5gDMAqul|`vuEA3qm6tReBe_X5xu{QlrT`5!<`8(+nB2UA)sKaa@A&$l5EAGYW%5fNX4u@Bs+mV>s'
    'b4GWIgke0uI^fO{--VPN_%skada>^pMgN$}3sTI?b!BS4Dv8b%rmaE?svuOUt2CE^3*52gOoto;CztGys3DkMpiohfge`Lk*Geel'
    'u9W3*QSAFcIU12<?Jvnmwyp9ruJSL5-@}N`#S>W%#N<XQtvEk+)*)#JqA<p7f8fuyL@vl(htp5{Ttd9>gNM<+6aYfo#t4c6t#M8_'
    'q6XdkFG}P^JRe1}!VvfWG-)J80a8L8Pk12m=Z~j{ue$67>5RfQNdmKx>q=e2$sAVxS~2NFzD{2d`QnnV=>Nebao}T}a6s;L^v(DM'
    'k;8%|&<<cM>OmqCZIVebN32d%r4r?FI+=rY@l<lmQ!^wzm+)XA$*VUY3+Mpq0s`(0%GFDV%RW$F8~Jj0B#SiCcr-6Kx>Z_~a0`EG'
    'Q%@mGU=tvW_=g0{-K79WnoLlEB%vN7m03nradCJUjWf$q%7~9vrQ}Hn8pMCVb0-jKBj=595MR}I)MfvHfo&g<#3x)?M=bjzigJ#Q'
    '$KBHzjTP)DD=Y!$P>D+TZ;#fA!tTJ*3U4SAd#h4Jx4eLn|3rc~`Ft>XU~vGu(+dxLFkmSjneOb^)*=eOS40bt@C9`$y{<^bl-5!l'
    'ZWY;SJB~R)_Ol!*PGK0Z_6mClvG)VgpC(EhVVp8S$7bG9tmKACNR%?10z|!j3Q=vjTFQ5cY7@E_qNp}%DFyGy@5+nV5{+w6KG-^5'
    '0F1HkV;oUzJjA8_tQ)h?6`>F^lhWm<MF^R;g#b?^H#k>uZvAWoMN#_ITR{=?-G9ff$*#NJI$Y612m!*-3_7aLMFPjbI;v`f^2n*i'
    '4M6Hom5b#l<JVCHg%kF}3AB%aK|Hc>DFAVE7wTkCyk#))hur7!>yekPL>EzTt6YI9B2wPK2vNR=u1fiF!0iTLIw=POa>~ItJQR!~'
    'Wa9RLG@9ZvoG{|l2?IQunD%k4{W12RQSAUmhF#q@aQXY^0_yvyqK$AaJ8auE=^xBa3EJ$#u&3y(IB{nV`93JQYR_3;SgEG4DK-ss'
    'vOvW)sdDhuadjkztFuLxxXi;Qycxkpo81ZdC34VG0&7bI(MF@gLKZ54LAEH31q_=-Mnz1ZD20(ci6RYrq`AXulC(UYr1fVmWn+%S'
    'CQ43e7_B9OvQuCXsWJ(>9kXmLXvISSi=BrcdJat>(4b?OM&MZhVgy!Zijv~W_>eAZ5F?#fBd8%V)EH5C4A+uxyQv3Sm_mz~i@Zh('
    'Nz`(y6`v8YGc_Rw;di#DQmyY#0Y|CKwaOwRU!@(ht_j#Bo>orG`ejX?ED)wcxcBMW5awV&jc|g|8X+)0py&ib*#u&oQB+b%d{jv-'
    'hprf{&pc7(K+)dg3T(`RzInFrkwUcUtmZq)`3tkVP`{z*>9V3Icmg@uR(y&_qm911fNX*S22r4$h+0=s!cZLnH}EimN|LEk;!<Q7'
    'aNq)Hh$9VQOp;avSsMOUz%Ul<Bwvt1gpA!4NNR_r3REM=Qi?Q#NVSznvYDy$Wc-;W6x_-hLD?lZTXO80#ihulEIpN+u+L_HA}7^L'
    'A}A-7JaP#sOl{wweT&(~uz7-Q{ilU)-)E`cBi+2C9H^BqJW`MkdJpG=kch3C8A$87pCnnfC{1<xSsKE+!5{`;)*_Hs%m>v;a4@0v'
    '2a{t6lLt4n8V?^I4&Zj6@CN5vG&O0FTurTR)x0`P=vvUVCuu1db?q!47?Z43^}s49PwN(0D`K{rTFAn~9>zNJEEfokG0C^bQy|aj'
    'xULC9+NmZaZgVXw7pW{eKPrc114ksMnpd%DyxgcnEi=mwZy&O(#ViTGFfh>Qh(+0qRa3)=F~?zQ^3a4sN3vKIx@#p1QI<`lmCq>Y'
    '_hLWxB7Pi|6PCm4l{cP6?Qy!DqWwiofoVE;@$&O~$u`K;p;f|Mt~`LRRIaMLe6CDm6$TH|jzSt~N~T}x7m(%o4W2Wx&zU3)`MnTV'
    '1YrUb<@yqMHbMhN=n;h`y<o(ma3iVg=Ykt#%z~;HVYgM7dg4A}%TAV0LL_sPfUl|?-oBh~mAx*P>*Xk@qbwJ}j1+!=7w+JpFxX=#'
    'LM&5QgBuwEBnUVsY4<JBcI8nC&x|eF(1QnBbSVg0RGgcrk(#eg&tx&j#r_{uU^K72Q6sJS%>C>)vLd?Q)~cw*-8D%~KD*lPH!7Po'
    '+e^AX(^f5*F_MAp?ARtb?nTXstmccFOKRUw%&>l&qI(~^d-sDAR8AN}1mUhzO_`op%>1PHk#8#dU|n{qx6`^DmgU$fGnTpEWVzl`'
    'wmasn^3MCm9py0qR4(hX&!QhT%2AZ7EGN<bbJ=Pbq@A-aOYYlR7qM3z#>zUPf!L*>c2$82;>AfI%AMMjmvc|7L0OKX95%|E^H9x6'
    'Nzs<&`rP^U4s-9``RU%hER3YQaOVnkk1R~bzB3M-V_rQtJ+EB07$<!5n2m>-V^4b_#;8&-P?Ye^O<0D~(jBE2UT|%~zP?DIsW0-}'
    '>#IUM(6u<#ywagvtA+QfMWPeBmRY%^K?QGY)McxtaF1;*R+c^5TA=+`KqdwSI2_n|-{{H`OS<avK%L}VV%e0`YPVQ#4-d!<J}@_k'
    'HVR4CP}SzE>ah4se(Z~@Y3^cw?Psf(L`}_?YcmVu;vH}{9`tOSJbS_%fcdL@M;?W|LG&xe{tI|EycCWAmLNiYh-i64egskaS;>u;'
    'n$YtHuqlfW^C1$hXQBmRu!V|5HNx0}4+o^mVOj^t>6);RDB_kup7CI>mpr-V#5E79xzmM6G_$3@7qDq`QdGLKm}N~UU@~*;LvC1P'
    'EoNDhOj%aS8*v8kYPa)>bMi{A;fME#s3~1v_ELDAos@uNiS9ks!XzCLy{ly<(bkGOYga8tN%B-~YFWuxiaOh?bFQSy0b-&{M0{Pt'
    'IE({9uSu^%=WVxmVaYEmpu<na%m37r^Nut3hODBdn`iDI%5fn(nWWd%sq?pz$4qKd)_I~>0pnMm63nYhp;0++B#mlDc@raC2lpsi'
    'UmwMlqOZt;`Ep%eQIV=#C8TKz5kg{3x`M}ya^(u?^`|S@UWt4KZ2;1>E2BYmzT)O9B>h7(4?d5;l_IVT+vNF*(D{&_UufLAWx{+V'
    '$t$fvb-toBcVTtqX}(g_6+f=9Nd?Xrxyh*`&Gwa~uf!c!lyG;x!tq&wD?kr8X3yp;7@riR4i8=G@G#6`3N3^nv`Y#NA_;Z0FVgOc'
    'YvoF<a;-q8KrPx@=2{S-s=jzzt6UpBO|@uinQQ%~RP(l0xi%uKQZ3qA=31zL$%wN>*DBZAP0w75Xp*w1k-@50L~BuVx)!h0f~xr|'
    'HK%LwN{zHjnQiHqA(1slnx#LqnxzxSz?6hG%1t6D(L}WDnG>1=DSwWF*=6*%D&$-wUy<0|TCt&xS6Gr#Y)w423R%|8S`ccF^yzDv'
    '&n$jVEiP=3bxrqRR2ZqOQc6m|B~KR094MN{Cf>Y-g^A)Z^z3mOd5f7SjCcz??6K*Y?zX@vhPx+jKHaiZFlpIg!Ejf3Pb%9cq%=Y6'
    'E%MqjqpW59Ult$z44M9SnVy}R4cWt)0AgN&o(bXeJ@iaVmdh=*?VHfE_*u}ibSFKt)U8~hZutszThg;6EY3A`i;B7hjH$+UBgzNO'
    '&K{*JD$3+AsX3UH_QTjCW<6c?R~5;Wf7J9es6T3<i_^8Bm9nEf7?JrHkqXC6DqNpWg|FDY<$EaRmGmzAINfGRVXd@kQLa+Ll;-<n'
    'Z8KAqE#6jn(`N8q`@y`UZ;LKRI)-G=Qsp9~nMK;TVU%hH@KG>z#zNeisiP()0gs{sE5@e^X!Z{9U6rj|p@hIonTRp_u=5D8J&cg~'
    'iDfHxohoGt#u?11P|@Z+l7v?hfK9@aR>Tk%%Q;HPreLNJTpXQPhYt#uNLlPFapBBZixSxml4G^w4J1}3gW7I_)^<^LbQo<LXhrv0'
    'XpReP_UIE^Xv8FB$VuQd>?}L<f7NA@AjopeA+O3Ihs5PbWuGJKjPpC$H2zGLt8&57HWM;3xjmUi5icV<T?>McB(c3pWj$D<e^vX0'
    'wak_&{(7wl<1lGstF3HlsD&X#lDyl(qhZDCuTG|A;V*)b+>d8+RT)CODk73(r)z=Tl8f|llIA7S-;KI~jE;5fir6S9u~AU*ZsMv2'
    'kB>>#B;QVMQ1E!AGxW;S&X-jUJTJ5CN~*EXA3Z*%Wi3<+(1eYt>ewi2#g}!>ksuIjA_Q8rwQWbBsixWYt=i<2q-)n)o3s;@Fv$H6'
    'O({duG1}>fvyiWVJT!BBN=l<Tw4x96@=D|@+E9uEH4s}WW)ELcnoty|mem!%yn?7>PF-PR^H9W8gQB<+#g)icx=Mzkf?-&RD_6in'
    'bxg=4=BAjUP!!V?yjlC(Ojp>|x_}3%ypq)<US0uj(=$6Jf*<H3@3p}3h%4yco)rfglp}Z59&%xIr7W*FrSZ?}D{*n97?VWd<ww>X'
    'SFc#VK?;jWuH}EKv@)Jo5MdkYTC4`et*S68k`xC;Zn0bV%$S&nR%M1UZWFWY#HhMmnoKZ5Js{SL6g0#vEeRD<W&{L!%hNS2k|<l!'
    'i*Uua(oMn(Ev+bu_zI87v$&0~QkF9GPQoiPDnCfk8X4CPLJ^Wks>rsX3wl<YbWz)~iXl}A@m6prS-h|p!V>IR1TxmOHXHwJlfNMI'
    'Azh0CZbgh-P$pl*Luf@*Rfa}}Ptcr!upf$w7XTfhI<E?AqN;cQr1tx)c6hOi2PTb9D)4CER+Hs%-@ZNV&1LuA{8Lub{i4NxTx-+u'
    '&sh-@yD?D{s!P<<XoQsu!xL8*WpdFCf`t!ao+0~?gr%zRB@--zDvR3$X}Rqrw{4W1wbl(c!KI5~)YjP>w_JK2hJCl((Xy>uCUjsx'
    '5hRlaEEi#jRII}fa0b~he4c>fNbokrVA?KkIQ)b$#~eHPoVt?_Ap1wXSuNz;zDk)H1D6ddnW-GfY>&8uK*)w@2ui@RS^>Q%Yt3FZ'
    'N}MTuUH#$fmfd#Ci!MvG)s6mPL`U7vvj63{xN&OE(>O{MpEIV4bvin=x#W2+J@mQ6KoXJ`%3Z)M7M|QHqOn$;nG{cfln7)FE$XNo'
    'oC<IARr&48(J1AT+?<jww>fjLbB5?o-a~(s-}S5+6ei7HIe#aPG+da;jKU>53eTk|$bJ<&OxY+;LWPa8@#SAG3~``R5G+wK5n_D_'
    't&n2!lQuTR6KW<0PCo?lyj4WOqel@bLx|1%td9%xSWCYvTlNc`rsQYD*RR;f_PG@7Tmqviy}zruB#w1T8eZn|5H3>hP(bP;oErrE'
    'LrB-ka*)>Js|IXqeC1cl>U1YL04Zmc;{T)8CF=5$LaXxq)S}!hBhMhpkz)fmX&5k=9kwP2!hA!j^pq9L{2p!o95?2VSx9*)8{B7C'
    'lUHU4bzPR@*hFd!IV8$SjI|TAk;|coau$xLNja>_2<T)6B49{D=JJ3!Vy%HZ==Ou9Q~akievfqy$+fq<m#n^4*{|)OV%5rGiW2v*'
    '!AlF)d;0B)(AaXmTK1EoB~2t!1`G~)qb!YNl)+3{il6EZGE<F)U4vk3IU%K$m}(1WMh#xvSg70Ov{81J_%bX3D(*Ayz2fK-Dw9z)'
    'ifJKj(_#WAXwhkVE`_|@JXBxF%jw2t&4%Y&U(s}Wi{D8bJWkr$9)d8m6OJW;%{IzpbV>x1%0)PqoAUDfShmkxca)<lS7Vnb^*Hkx'
    '&5I4pGv2=5%toiAiSN}Sw^cCRHkaaRE-6?nBc9Sh@^m@vDBCewltnalFGF(|CO;uhWg+#FxOPHbJaa}~iOARGxZ#Sm!A$!dBqVO}'
    'Z(C>KEtaq>7iZkuzV2RmYX)z@5VpCLHh83{4SN?G1INE`5TQI%9}@$|Wsgw-OgU_p%SO4<J%d<lVYqV=7+8+-C{rd8m!Gy@wWUkY'
    'raWzUZiaaRyb%$YH48uIBmm>tswOJ!t#rtcmeJRHNtTl-M;U2Lgy9N|&x2ZQmK{ZT#xLt_oMlAk^?BcG7FeCjs0%SVc5ed%r!r&8'
    'Q8uVtX;B1SPP*)GrTJ?4W;)|8Mh%K&%l*~Q!tBora1%CGsn*!*=9w#QP?UP_*1zNH`3^Qj-+axN>V56!T0Fi6h~_@_>_fZwZ`;L='
    'i{USqA3pkqnjeR?B}7wC_Tw=;@8x^#9v|C1x;^FP*O$T}w0jgH*<MVXAk2EDaW8a`h<0mIp&Aq>Ln6SP{G&H9H-4$L5dF+O`RF+L'
    '8LLEp9EKQGp9FB#Npt@1@LzkEfBhf-i~760&9HS>WJsGx7h$l%zEwciA<ZJSy&j9X;IjM7|7-p9^@jM;$K0njB`@iRVLEU<ea$v}'
    'lSV4IHc~y-3q~2F1$~ngiml~Y?R)VP+q-;gg!6=VNgt1geY4KYz-%_oyWeH;#A~xXsM(&Evt1GpFKl8a>LO=;>yuw-_Be>Xd?^g}'
    'E~qf23SpYG*|4%aL-0AoA@SJM0m+)32xc6SJVuf@dpt!GXA;Pvd0h)x*3dd^RjW?a$bVPX;OQg>@8OqYqFSUHyir96;C9|e_v=gQ'
    'yD<>M0Hu&G_ojht;S0t~_ja{fU~uqQsngpn3)Moe;rS-yv8|C<PSmQdIZ^BG-Bb&zMq4GFzPMHg@f4&pR;&#|4DAenA1Z>jhT$?m'
    'W1J(aQy7$GQpf{EZ*%i&#5y)ZG2en$_M=A;0F*B&3zjvk<yoGBoVH#o0(qUwH5LDatn#It$)5UBMq4y~Zcyd4QO=@VM7hdxmF1Pw'
    '<}4{J_a0{!IudX7#Mp5~DDH}v<tI_jvK;r6i!EO!FqNa|=h*uY%|}}wk{x65d>TWVrTRzPp(}g2*O+ge@A;qqhYfsA-N1*0eB#-0'
    '%j80;IfcP`5nzl-9E}oVUREanuV@u+iyiJgJY-{&bgldr9?W~6yQTEHUEZk-OT60-E`_nCgF3QelwB1UBxv>dtck!;Z?oxN{`ZC^'
    'eXaf6a_rvFq+11V@+3Ja!iqaHYsOF}K+d<y!g**Iw{4ktT|u2+8D~kL_N}skTiq&e$?`@yGaCo1I~GwEu`;57g&XhAI<$S7^d!{b'
    'wtR;seak2eHR<1=(0vVD^2C-rGJJ{9F?kczFJzq~$3&b{a=UJ4Z?ko~FQQdDZ`b<&-?XF2aO6!NF9l$AhA0I5Q2E}H!=I!GN|qqf'
    'C?xRWEa4YvqV3|fQcogJo$8ZJvF()YM+Y^2M|kTXUA2VmIGzL&Sr+J{&o3|fTz0t6(;YDonRvJu3eN_cxVkrAuddVZ%6-4_to2lI'
    'N^~Xqe>zacB>F_m$h_I%(C0r-NAM>2fnd;qCEM2z-<!wrIgR3&9+j-yc27_a2F@I#-Bx<_Kd)r$QhT^gBjXH?-?qN`RR)|r5#THv'
    'cd{3JauPf^d$a+qjJ8UqUPnnDi&l(<s&~9tmDWl;+G+5#VsdoAPi~5FLQE%FD`1{C@}2+rs#S7PVZ7YV*^xDg`?YcS#o;6ZeAZc5'
    'nHg(*DHB($OZJkxPfpq+Nu}V>5~NklU$3R9CYfaI>ZPm^ygKs)?Ut)pUgJQdA^;1?BZUByXKdjloP{oF{1Dinr*Tu1-VB}-SfNy5'
    'UXN}W8WHS>0M2`aV^O)*9`eXBWMY*OWkQvh#l9*e<IP%D*v>^^ZC5qlg@TVQ_%qiYm34!cI`!-%1IK=El6!4)^H&;;=pkYb>Eoqv'
    '7<_~9$$j%utuh4lcIkavwIR;_m;X!h>_eAlA3lvdn;P`*+5nDFyN8dL!lB8enZ>_edY%8?^=Tje<A4A7;pwk_{G%WI#ZM0L!#Dr='
    '!(TM=+C4%;k2(_)lGl~xSy&%e!wB7p<bqbH2m}HC5a=_zQ5NgDIt{wBRgT&^r>r#DRiNrhZ2lmksFNXjEy9ymhc#T3!@hFCc7`bo'
    'qbN5b?7^AnEF6o@!lBG@WT_&sm)MZWwJQ|W{BgwUYd)424*M8Co*<0X+Ab#E>R4Ad%F@tIDZ=88L45ZzTcQ*}`Aak-BcmURpy*Sq'
    'r2vs{cmhXJCcIly_NJT`W%mwccSqTa_cG-y%1OMbEIY;#M$o0~C3=*Sp}^sq)dMFRPKQZ(ZlpW`A-fcika;ChPs%>si{+OH0E}3P'
    'LT{c4XD}0hM5eDKve8af%C#zm=all*Qn4kk1ei(L_a4Y|x}x<@EYeai*g2k*4RO>_9m(~lD3g>nCQk&EHE0jPR2oB*u*6UDYdhtz'
    'WxrgFMrm;$jZXMU%3&?#T?iJ@q%{&Rknz1dZVid7?1a%3g{I>ZfGQIS@OPHqfh5&c*_(1&ltF1k<$`}*x;H2{2?!}sBHf}>1KO?`'
    '{}=SzZEhC=|7-N-EEuO`r2l?_g;&va5)Mr`c8s^qA&eO)F{(fKsZ>Qg1TKYjDL<FCY*CpldK2gX6%#O%p|0tTx16u;wJmysV^Z6g'
    '9FX1|NM)_aO0XK*rGl>td&eMHTTkni2tHyrGV$|ezv1uF0se~1{<F(r?F1NSbm>`d6JMzfKg;FGPCHGCepznw`9G1uI*bss39WZ6'
    'CN?2hJ~C2I^WXq(te<-d9dyn>3p?S!n2r5Fl&H)Owshzz0;Ba+$|_(aNLr}uc~Yu)hh79N3hFQ_b*fT@FFJkUu&{7GT6hj9yOpdD'
    '??sfQgh>*zIV5Xb1?96pHoO3zLlOx+XIp!4j1rp`mEF2r1g3Nm;1^k7o*6b?y>Fa6%tZh5eE!QepA#KM&umlV+|mm~TR><yCWUTp'
    'a13=#BQ6;$&3L62KD%0#NJLTKhZiqB9@x);j<sByqOxDF2>>M}b7uT6C5Qd0c7Lssw3^ObUU8{dYm4ZwC=%sm^;`;L4TYlYC~Ra!'
    '{oL)`{>~}nu-EvH1lLLdBxs_{ebs+AbMDK})j6B<HqQTf*q;NjJRCp9etO1G-NqLpiX}Ox#$Q69%06rOJV}2%g@D2oh;3a-!M^k~'
    'PibPQRuS6f#I7sF+5-q%kud~E+8_UV$V=w^QCYgj`r`dDUfCaA{i1fnYqhB2@#>mq(=8q%tVI={PwcYHItBsEO1rZ>HG72%8j5UL'
    'RB<S!485>NS5UTNp<1_gtCo@H^QdZ}O1{BMS(K?c8L7LNNQJr<B)_5bx3=c0+J)kEE}}Z8h2kjL3o0sbtuopy)Y>BYL8F^TqMHwP'
    '5ydJ`-cfHj)oeiFr+owZf;Y&&xeRpla5}yeLPV=Qq`C~W6oqiGALl%6RtSPRv<#6aS&pc0L+bH_h66@`hzr$ER|e4uC{l!D8!ic!'
    '+AgoiMt^nX^SM$9nik{>g9r`Nks*DUue2HaU&xlJ$#c$P#yTaMh{E$dtH7^0NbrXorEDNi;1OCzq|fR?<oDIV?kx{?NgeEpI@lF?'
    'u=}Bs_65=?tg#-v!g^q4U|>q}VJ-^OC5dq#1b&KC^ZKdm1-~?x?XTWfac$aAr}9>7v(P6Ige+rvW?^rcMTE5~use+m_bNtA8{Z$1'
    'HZ=5@K@YV016w}|!_6d^k|&Gjh1l4YWd~B3MJ9oy(jpob1sp;UWpB!9QFiZ8cDKt#v~#PRMLCI+Xc8x5LI0#RLUva$bOci_r$F2Q'
    'oBPbmy8+i=4*%_X4nxN>@@I<K*l~C*2B*^)YPGY_YUk%@wd+r#R@+ZnZNY;~8t$a6mAq9$WWg;YCNzbu6Ut{`A#s1%+t`$DOSRVK'
    '@ZU8p@d-8eC*;C>7Jf1)$jKC%Fb9%xMJmxDqSDxCO9N#?!-9b8YV|L^RE^<iFphFaO@2(~w{0XsGo$z*8J;l5CG-OQtO(x{MpyDI'
    'eX9fn%cV#tLy;p!68JEbCX+F5^nA+@iQ2r!8+9P}M7A=xYP!)gavozD5%h{ERY#U+TuNj{O&ksLFjbhKNPD=V?Gf7O{5@Gy9FHF_'
    '1@ycy4s{WM98`FA$2_Q%n|N(tS#VRp9G4BLxW6E|OSO4JW(~?5r|_(h0)iqf)@Uq_Fb@A<_FOy{9MDlmNE9MT!;&hqxWiaS1+l06'
    'jF+n{U)@iO2HbTtm0=6WkvD<F;iZaji*js9_K$6Rhrlv)2$)OyLF_0=mf7X3Fx_CLmg1C28+r;T;&nig{?)>JDV4K`CYFW2IYnlY'
    'W#~mg``Hcv{lZ4%CZ=|>oCEWn%W{`zr@8FwI$D7<<)tNh-0*JSisiY59q$Ce{I4xQ-2*JtOQA6qyxfuDo38|#Mu}BO((OgK_^+-M'
    'VR4qVW<n{jCOLb^OroQ{!Xd!K6`(7L&C+VrS5m){<rQBdhm7mzY+qyqB)U?>mE6#K_)5Sl6dS2s8Rmq(sHq{Yc)Ie)LX%Qe93{`^'
    '>a3<r(3ZtFugJr)y<#SvHVR7{SBkM6)R6P*D?!3E6mw-^H2>cQ>2ZVdJaozvNu!dTEc>dB_>1FEo<)S+sybd6M+?g$6lZoy1;y;1'
    '7(0%2B^^4W;q{eQ<SmQujnl8&pd>xAB2u0#PRNOWT=~hq@@NO41dEwfV2V^rzKCBTFnMNAio&}*StpNj8^@otaeNS4$V22UBqDzW'
    '<;Vw<<Rvz+jLTuRlRA~14(q2v{E0A@D%f8Xp(}$f8%h&J+(1QLgbkjc7QW2oAmX70h#rYIRppicK;4*SX2vZYjQk$x^gVbdTky$#'
    'BQnPp)O_54npXh}@qU>hN*ZF?$^|T5S&r#OM`-|<B8kyIu?J5g4<7z<F)owDOv_SMC6=O)oTbRPeV*nZ&&Eh6LM|ymueIz|C*N%8'
    'j6%3t++;dFM{^T?ek74mWC6D%zk!$o#s-3)%F?RW!lKm1<kuQYa~R6>hmWV@#|MO_(Oi%*abML9%-pJ;jbp5>7lk-5*XxyfSk>ji'
    'cv{reBGUEFmP@Od6t$J9S^}-E0(k{nFM8Lqb-9PE>MZ5wwH@brm3R$dyB=(`+p?%TD>Giym7DsaUL`3KJE^VfeLdKE(R0SuqY<>k'
    'ta*UCQI|WPlZUCK7!6-F;}NQ!#8H{;D9afXeq`M%s@@jjuQ#O7P8=V)MN3<U-gK(By)3mwH@+a>UuiWIn;T`AYQYAYdYtP;*2CM^'
    'Z?z|x_S?GC@2_JO&(qxLx<$sbf8QD)?r+<__Wi0eQnjS!FYEeu)!#e6(H_63C-eSE_fIwbS4{tAJ^vNTn*>j(GYX$lfc-{Whv?G!'
    'U|d?AQ}JSrXG0{U6iEV|nHtWl<@HSRQiH@ZUi!mG=>$WkN+1=kN45b>$}P>4q+8Yn?4Pa2tOY8z9<tu*ZQW;cWOMh|{byLuchp_I'
    'j}@BglJh90o^>6A2=g&lo0){H8yK^GAk{1LA>t(9MZ^y=pFFEek~-l>=_Q?50_P2(R65VqdNJ0sieYT)_%|D4dxZTI_*!q6m@C_5'
    'HeaagFGSV_8hSp_GfNLG-K<6nqQbR%Q+KRrFHZYclxrJvG!CEA;`i>l<UsuwSa(<IJKn!st1tRHU#l<1+g+)LdH&e>m9Fp;hTn)b'
    'u&fCtSG7&l;?HThM%z04cH2+Uo2e~DulCcRkC2+GCS`DIYoawud86%nbUz1G^H*xlj91yN1y%E^=5$TWp*S!{BO!IT7uWn&Z9&1F'
    'QM>kpsrEW=1hA~42YueI1$8Els#dpaUe$tG=X%xZHLF*snswS*TtQO^!OW_*<tfWfCA_iof5*PseygoEkE_iKfP|TO)mU!9n77-S'
    'el@!@Mq4Y)eDd1cu6eV&r7J5@)q<+|D>b<iUweJ+uYH1*_)6>2eNnYgXE%O*@=B{(TSMO&BGIviP6xY&%$7wYinyw3Pk_lB@hnHX'
    '=6IE5AfK_k07yyVgy)%JWpx7d#2F-67qAJY4k2Ww6JK%q1i`VC%?Z!c-Kzf6asq@A^ID?Eb<Y$&OU79pG2F6VuGJOz(4rosjAKz('
    '4U~r`uYge%=cxdPB@nSZeR&y^K55YoD&mdsWzAep>%(|RPA9(KZtM1pC%&^h@g+t|ov$$dP^i_sJvY~$1irfRW>?Ii`xUQz)z6>D'
    'm7tskirk^2KI>gwxoy?|4nu-HG$U5I>b>@)5zqZpa`B(_Tn;jwduW{6c>XRK3AFJ{Eoj~c$)zn3<bsvReN}pgQodSBixQvModl&C'
    'F#RYVCi}Qx;Q^x#<zqQB3ZT{I(eIJ1X5$7<h8qaeYzot?^7HHpMvo|t=t7!cbj^%@s^tjkinP5ECt@x0vnQQ6S-wuzZ(iBP6>Vq~'
    '6&Qv*F=lf`M`9o1414mL&SKs~a46bX5xi{duk4x5NcqhnYN3<8c16Fbw?P<+vJ2xY*|gbS36mAFH>$s)p=_-lUP@xK>G^8rM$lTr'
    'qD^6}20|fV<mpOrR_|P$)jTh*=v6RN-)J@3T4!7I8lDzf)bR}jI&m=EfVk3D{qHyVS3oO@(9iDI&iihmQ_5eOtmCWN&05fV*Oi*l'
    '3T?~z!xfD{-L8363s<xgan@t#GjrV5jTlXd5Q}N4N-~12wub)TvW60BP7_!JRud*sqL4}&Tbzz&YOvVVRa25g%Wq$uis9a?*?wW;'
    'YSCsU^VPh06=T|xSf;M8CUKP=#8y{*b+@i&0%TramEcd=Ev`m#$BTK#RRq*uUrkD6A2zQhG-$nX)k|P$d$kw^!RFPX4B^GqY_9g#'
    'SYK7@qKG#0>MC-SXJwYjSLNv#`Ov53Rjt1z4)va^dAb@mucqm0xbvzsUvQJiFikc^d?yf~N_K$(!dO0+1eh1|2t{B^%Bzi{{d<<^'
    'KXi%yg`x!wmTmodW$<F5zZ0hbLC+Wq!Pcv-ryF$<Zn7IF%cy{v^lKY+9Ka~zYGhIOi+T}tI-X~}mQ_88dQkp@h)l9whX-&SVufth'
    'gK#T~8702k_3;2vj{>V=RUarzS?WD%G4&d=wuF*(J8I!Z-J80*Rgb0~Zq&W0yIb{W>S0~?LN1?;3q)2swypOC+1BA7vQ5^h+hj%I'
    'Yf!B1zDBI9+Hcc_6Svrj(tRLS>DVN2$~Ba(Sl-rlRvD`sO^Y*<2rq5mlhmA50WHcMAI-6ByDnXrpIc8R=*kyS&(bC5`E?C`wyU1y'
    'yoqyND!3T)eyV3V$Hn<K8=-iT5-mAji=0>S|F!pS%d+guTG*?=3XZ{8AdMVzO7kZO0x&i{b3TSI__ZX!U>k!^*s&uB-hyjxx#xaA'
    '3QyuuJ-VxunO~+<)!p;3R*iq}xk~!7yHzTcl;^zZw2R>ynZ)}Mp%SIQSe@lP{p*|0*1Ht_24WF}=OlM?H$koW;PD3BJB|DPb5FL!'
    'jE%4rxX0hqTi#emwyKI<Kr@j<VF2N4Q?%DWLKf9>Y62eR8}c{U3HIqFQCEP5C)}n6ytqXOnsWJ4GP^v>Zm(+MDG-9JrX|9+<e8>V'
    'HGQtBlTDv(`gB7<l1VK=uZQF|dPh%IMaF*M9(Jnfb8c^sbRjl+3ht4oV83jVILP=>cIy$#CMp{fsU<;jT0|Ao!sD^mb5b&n;Ehvn'
    'Ws$EkcfJ(Cra{(l<_d21F;1j*iC)>%f2^vHsqk7sM4Cvum?qUldP;N;Y29K1m2A_xbN<bRr&zsn!o{u|Esq~7+`=Kq(28Qj*QJSg'
    'JK4^TfBiGs!D)l>x$%-o&xf2ZF`s_?W07_>6~$JBolC}7%J@swmhq^gwi~aycRhf1^V$U3c}F`=#7Fl26T*+;rfU+`Z0R+j-pu8_'
    '{97L-o317GGLLsm{noL)qp>NmBI)9DYbN5Zyyew>HFh<pVizbzoo{&RqB2tF3Ep3GHSXpSzQ$j74z#hWQ*cd#$r4Jj(rsY7Oq#LI'
    'l8GZA1+l<yX~8ByR1|C2zhl&l?5&|$byJh9n;J_eU-x+|dgiV_%)8u9-F2^`TD=H9uG@CV^XnY8Qo<!{C06R{AVOWj>VA5tsU=ps'
    '83~+KxUB8Jy~Wh$myiGZiG@vk*11;t%5kZRl>d9%4Yjuoud6uRwR0ygqV{%|B--(s_QYz3*2RBb74g*T?GtD-2260<A)M{At=f`b'
    'O@ddH-Z@Q_#r!*qlzsE!c)$2`%UZT6l!|N<&%v7eeOxdNETPreKHHH+MBH5Dx^^|%EJJP+K7naAW<Cj@Mv;;@u^Ol-TD@|?&D0A^'
    '>6f4@9k0&W`&9nj<-H7RvZxP3swiw)WLvzbIm#E4#DgI5AflM~K3Rc$5HNWGdJw(;O9EMna_58DwYh~&wn=0ml5HnTQA2H^$}-z1'
    'OHpy!x9pbHYWKN9w{|Lgzvt~7xSpkN$3CCmtsPmCRn@N1POWkokZKoOV<VG+#X&nrc?q<o8pUms(EE^9D9Lul?d3)Mdy9+Kr`wB|'
    'lYS9zW`oLlZx-;ny_9j|u1oA0?6Pw6q}0DRo|LJ8BU4nGy-n}9sqYPJx9E3c-pgM7#(Je+DzW`|bu#UHSIr#TGFC<=6`@kry{j0~'
    'Sa03@p+c9GS@o8i!$$Ud1MiK@MtC!q&iB?3D|1r5!qlBHPVeP{`oaKo)9-ZIom*aelkBC<A>%qdH@^?v`*G22dL`W!SHBgOCVRu$'
    'XdelJg{W`#3Y)5QSloPmk}%Oor{}(*dW+r5QU~E)re>e$6`FXapHDNrqLje3u`Pme@AhEVE$#0!A1%7<Xo<PH)*#!g^2VBTzi^va'
    'm*b(^#;I}NQmR~4BAshG_s~A9;-*(4QG-5-Vo|AZD*@BTluqez%j3@vp2V|?1rgbhS+)DCC!t}6RJH`*3ZT^b(ir09>4ZmTc78w%'
    'Kn{?k??UD6R@fKDj}-ddiWhHI73Nf_3M_1dx7;8b>%}?LRQVKaPGddC*+kyUB=TG)k;ihYN?O<)$1c~bT6THMu63P5>H{pUbp|?B'
    'T9xhPJ^Tlp$B#X0aXb66Y$wk1_s)}Xb(-mCjD+yi&0v!W$FdNfGMlm3<TlDzWyf<j;RV;a8D4*&=dl3~O^q*m5-G-6NY?7gXz|D;'
    'avr%#9+-rsQu4gb;dvpC>%FLHCr^8}{kE82AzX_<B-UPD#DBPjGUX+d>HVerNv6vx{O7e@7pKbNEgmN?Tb&1V*p%;O)pD#Y&LMLy'
    'I<r<UKt-0$F0!wr!u-RTEKY$-?ph{OlU;)5jhJ{3zS8*t{guV|N}Byj?+0kln8#n4Sc_!{2|S+&vv(4+o)WjMGD|Gi?66kcs#M<m'
    '{&`|#){2uYnL4h27q}?>QARv$sj@y@Qe|DMU#XB(&OJ*n%hIvMeWK>AsOX1{s}CLS#QnZ>>5aGMm9;kCmo9TEY^Cvkl%r)Hv<S2!'
    'i~aa9Ti*SJjV&@;Y0rN$bNbXR{-h&Y1!9Hp)k89eYPah6iWIAruVl&NGo^2o@5x#qpchNF`f#^3&t(kG&|CWxmo2oex<WrDVy%Ts'
    '>Q&<1@5QZf=f^%E#&WiPlP%JVsY|v6vWs8CSzhIvaSLZ@BF%wd@+!8ABHK*`gEEo>X6-;6Z=zUcqHNKEEH|tWi-$?Pm6>ZVvl6uc'
    'G45OGwK(%^Z6HA^G>WA+Cs7fEo3;x3O0JS{Ha4y-Q6F0!OgbKRO>mi+fiW`)ICmf0^h-HxQQOpdKA$gxX1BN<kYJiD=4d2hJeX^f'
    'i0P=v>kmmMm%QZ5TSMDh^ZC$QL%^m99rhy|6bZ+~EDX3jIV`b+0FfmG2rSjF(Yn1uWxIQRhd~PG!D_inu9|GG9rF;!F%R3a)lzG<'
    'gc(x#*z;5?JggO_T2XEwHT1$~S$z;!-YT)`3%9IA9ZMEE*TB5(LbrS|$a|K6aXxEB{l{DLW^!Rst|PwxncMC3)6ueKHgvmMpOLWv'
    'HdS8wh?VoptnhbW&Wn93Rn{tfi~0RW5e3OwtRQ+Ste_XK3>H{2R@UM^)vUtB&FYkI<-Kr{j&6fp(`4>$RloJ%ckR(F(xNtJjhbpL'
    'Z^kF<Jkft7Qtf)J!7p#EiWoN7D&u2`xYK}>{#&#heTR$yslm|>$)M59S`{7{gl<UqBq3fk!TiX@&}WmQDib=d=&*}!D>)pZ-^#ib'
    'YtKv4O_SPvJgz55?T-0tcD!wp%EplLENTQ!?yAh#@I3jvy){WCiYKm1E7p7^ai|t!CZo;gM`^;CWAn+C9K4T}xzjP-!%K8|g(@os'
    '*JYEVj|7KZtQ$*b`OEfbRV9nICf?8y(_JTQZIQ^MR@~bn*{Y~D`5$6-eAViTTBU7zyXcVHgV?Nn-Q!Mx|1HYV11*Hmze5S0JR(j{'
    ')^+N3N2kRLuUM@--3qEjqE$K>hI+ncHF*;AX-oyQ3Ujl}%;e2Pl+WTo?tL;0b5^jV9w`GAQ*@&7rahw$@FX?wG~wq?v04L#hN<3|'
    ')}KVDMb3ViWNTiU=-!%a@oPznk}beDlmru2`q~D)C`Mg6s4d>8hF+kn-Q%X!TOxN)mbIeaDo(3zzqf9Ry}2`WO2)pb!^f%7?H|AI'
    'HZ>J`$<_UWLlb30Gy57I@hM2r2NPE{*3?H}l+eer<u3AhEk{td>Df}3b<7+wGgv~c(1avD-zuQhf|m6g(*roqoqBuCy6V#Pw9Y^*'
    'KsK2Q-pl2!`6A{2E58<{5n9IP21Dq`eJ+Q}ay=B59ip(H|IB=YGs|idR8FM9e=_?(X2m9WtL$y%sg|(jDK@IHj4Z7s8I0JsYU)qj'
    'l33k~K5=ysDT2E9^oZW-v5f8^&3bZ25+=ohX~;b81@k5NwLkLy4#lOkYk0Z*=clFf&%SrQE?qxIdU?NyZ|^Tw>@pIj%{IFgWwrlZ'
    '-~UadyL{X7TQB0bUi11}x1@#aw}SEgxqCzMx<|FnI&l5B^MFg88|y7~=*qx#B(VcS;S=~LmkGS(=8tQQ>NPo){&!8$sQ+C9z~R3e'
    'KM4Nq)wSjm|Ka|Y8UD}z_TR5-<b8JEFFq8#-3fD34{TM0^uN^SLb;u1rPFF>F{P;r(-SqZTvXxXA9jv^US{~RieF!sSMdGcp8|7#'
    '+wtFTcptx8?&IPyPieUc%Iivr9XsW(l>Xl}PvWMU63J=~{5^g=%f0`3aqpjAzuS9<Z*4ZlP&(JH{@u;ayGweP-?nhJ%j36sna@AI'
    'czxe?_RqJfD?u%BQkv>cxm%>&C*9Ow<tBNrqC<{1ets3PZ|rp4gznaj{sZq5+<rVL=C&QTEEB5^u3o1xwjg@8z@@dP$eyHnHlb?m'
    '38E*e9;&h@6|-l(i(dVHoi)Y=Eo^*cYKm(FRwulC1YK>Jye>1Ja#wWW@^r3&xhn&kFM$(<I(K}k-GfWlc(Cokg=<Xc_Ta9MynAqK'
    'PwjhR>mS_pk#Ey`v!{!mq<SvyU6lnGg<;P}5L(~!5rF3RtXWIa8lu6M-*q9!PMBZ4Y_@w(g)jBn>bgF-u4kM1E#zT+t*FXZ&wM?V'
    'm-_meFZ;kBTgA*J1S`IzTearCtmTthwkayv4hrc*wps)4TVE-$bglP&^Sza}vcB*C+mt~|E3#JD{Fs+k%6)5_x4G8Br?XaJt;#;v'
    '+*Wg2B_IuVatw5yhR6LNH-8EzOgT8FRByp;CDtO=icTx+ZY{gu^1n5q)Ygh0PdctjIo`^bk>&1brq(~r-hYr;Axwo`)b_fkzj3$L'
    'Me_J}|8aTuZxNX97pp_OP$xL)Q%NWm3#)6&^3ql2_Pz<fTW+x0sSmcIww=(wD(og)1U-fK0rhv9@rDB}9*z5q)?FieK&D+apRRux'
    '@D@wGJt49Tvcz)5ZYzWbP4Iw<50~#Q`=3fCneEpx%h4@w${+rR<wXfM3r5&%=WSQy$h_b0*wZ)MN?`Ohgl)U(%DfTFiJ)7#vjVnW'
    'QM6XWa9T<Gi;=PgSwT~JQG1Jw*X&}spXOTX{f<sc83gTC>NllZizNz*EKLxxxYxwP)q937GG>oN)nwGd-s_po1xp*=*R+NfWx|=r'
    'K?@so*R+#=4wP->d}{B77kUXVu>Y<yTwUb^&hD0}uZb0Z-Qa6xN0p9^ijIyde9ciU&+|_$3YoWSwCelC=W80#`0>fSJ(`rE3Yw&r'
    '`lg89)E&KQ`)WO`ox-Pxe|v>;1OKkJglGI4`b0eazg*2N#~gdVu-j=DghsrdnZRnzbTb)SFFbbh|M73UJheZKo?6~qz^=6V3&F3d'
    'p<VYYbT8W!5SW7g(e9kx`~D5yy6Bf$b(UJUK0~X{awb;WN$TyYd}3jZ4F99cQ@f={e5EU+ep7qq&1Z1Sy*%@8Uyddzh2$+!>-O)O'
    '%GY{0>gg**W$!km|BZQ8(R#}Rw~7xpXRxiHi}f#cX^C$pwE8j6e-V|U=4DtacTd>@D|l*}9IsPYKfe7ojkhVgh?3hfdF7T(d{vdt'
    '5p|9QRmwrs%cPsb*>+X<RpM8fyT&D!eYXhCzZ=rV0Z(3qyS46|>qs4+U8DfG@sazlVy_7)>epyXZS*G=<@(Lz>2v4tL^_MA%*-Qr'
    'XCa3NUeUO)Z*06BSzyYzP5awLwTbcR6|`AcSMOFGKN8LG9D*Wsg0AEs>Ntp8mLI}k>+^3CV~|-gAf5wb4Pjx<Sh;iXzGW}CsW`s0'
    'zApAPZB8eZ-ST0ss*P((m~wlC=_4gfzO^qaV9jK89V@Z?+KYSGwmPW~=BvG0wQKj~H~P@g7Fe2{#sWs8NU+rvtzt<+5-*~-ePNfu'
    'zDuAMfi%G-kHqDYO5A@o^BU4^`^MO(J5kc#@}B;gB^CbVJ*Bso_X~Racu)H<jPL3?0qJY@`g^{wNdx#F{-@Pf;`QPy@%rgGzB`Yx'
    '*Z+ledA;Ukd0o7J?tFw_?e7N}=THCBAH4kZ%Rl?q|MFk_<A3w%(@($q|9<+%@3a2p!Yt?4m-mbOsSgjMrmbO0Q7^mYCvXm$KA=zL'
    '%R`!ye#29zzW$<w`=iM4BsFI82jufA!u&u@n}GUZ^(hJZ$>_|FRrg07a=v|iRSVASPg?V3_2*%K-q{b7vZO2Lh}u{}iAy5*O%+i3'
    'R{gQze!SFG9VWd<Gk!Bvg1Uwaa#cM}>QfJjDCDZ|>-y|ve-vS~?0HnxANvfX%ELaZ{)YQEK~b&;+@Fm8?WI!d4fWH`{`BPjcC5cS'
    '{cTTw7V8{j7R!9&H#Fs9-FEHYLp}S}U+n(e_it%CQtn@%*#Gp_U#I%}z%rZ@FbA9+u<I{@oi_<_?N!v?>xv^qWWZ2|aFljS=IH=@'
    'Mmjh5RZ?HLu-`8}%z@r{{Fk5O>+4GlpI_oDX9|kL1{H@xDh~5h9KH%;Af<}fg^LXVEH)F1&BoeS#*%}Pg9Q&u4o2<JoQ2?F$-&6M'
    'VmtI~6$5u--vJhZ2I_`2SR<)tEi%BODF+mh*ok9$sje7lA!5anmQ+>@@M<^g7w~>3a8_0aYe%ts5YrVe$-+voi}A4Nu!`4&g$1L!'
    '=@3gZSk@SQWh~BM<=bQ7#ExV62f@PQvHCzP+I!F4SU!k_ofzSLzQ>A#WyJS*Sc3J=daOcSp2$1|@^WO!pH=PU%o1$G2C^wJ<8aYf'
    'R<#nN%8OkQH!Q!BsaT|{kvcK6=^_F(7#d0v^-Og>B!U{!)R6ml2%Be0&{aZ)>h!YIz`FRZWO{kO;EG)+b46EuTZRfPtkH$DMNpTO'
    'dS<L}S8vk(^i{oGLf-DaAj?;Sga==SirP+%6vUelWzNtnRIyPgHmbD4Cb_p|X}1;nWUPHI!XuRA#!>V;Oibe<y(T0toNa+S-rY-g'
    '_ogTHw*9^JJLqlC>diZP%Y;Oj;BEN54fk#bf@ZO=D_E-)Zk2b0XM2%ey<scGF3mJtIdpq}#kQAuAwDfurMcb=PcC2vvwExEk%44~'
    'Qsao(H>_?Ao|@QlNAO&T(3oc!N(dgq0h$%TqHx~)fL^a4-0YWA_Lqyg^m5F8XiMLuwiKS`T62{xz(7oXpczPP1`-X+muchDZwGiF'
    '*;1fB6$v(y+U`-SS9@&HV_!EtZ>HT4ZgGPZ?L9eb*FKR)Bh4(m(<ZFDGItzC$V8fjkcnJ(JiU4e7`^(XiPq@4eabZ&wGxmC)ETVa'
    'W+4$IZ&ZkQK4c;ZB>I<DWL-eQM}W444j}0O()J^9h~ymzJrqgb9BC(V7gD|%l7>iqGQw?7JCSU?a}H8Wq+0s{aDZdHJdTKLW~`)='
    '5U5$Us@N=R6h^AyT%vuWE4OU-2J*zdu4naxS+8p)<A*xO7jdsenYy*xiLeh=Rr{i2-etYwt%H;pLz|k&5HGsu(?y!8i_Y-#O=tL-'
    '>kOmqaZoY)SujU5b}oQ2Am;i%97JU7NAH}*b<9N;$RXCt9z~WxB~W=C`9fi#=~4-vpxV3*dX>^q_LA(ac5i|z{{)Q$ZN4|o_Gb7}'
    'XShA==`C>Ud1UXibcWxre({@X64S#piQOQO@AoCT4(JRk)EU;hb%t3h7824KChMT9ck2xEZ%b!bo}x3XP!TZJ8MgORHoe|dhF`)<'
    'yrkHiaET=R!-i8_#J6gB5E|3SAH`Uak(m3dbURlToXFYBq8vYw?KvweR}@SuPlm5uNs}<%f&Qq?=t}h(<>AgBRA(~={n5%trZ~de'
    'r{zmy>7p!s;A}tb>`zbbZ{Mar?(8Sr9}SgT!u@g9D=%a6W;yXawm(jL9U7{~YA7qKp{uOEBw^40?&o;+pZ#b5*?;!mc@CP!S<C)v'
    '@uM?gkURSqPW+#2!Ox#wzI=8}_ePw16vtI&&S}sT=O3$tHJZWDbkbM@x<(>w*0<}7kZ`!XG3~i=yWYx!uc}6_`K`CevMAM;OtrT4'
    'XA=E4^(KqXuATZQb<uUDv%66@oYGtBI;s+2teozr>Hd7Ezf%|`;3oc?=_l2nrF45&zmDz=Zoi5Wu1cDM#lwP~RT^2)HxqhRT79uA'
    '-ui`;^ePKS=*?V(4to<%liYL-?`A9V+|bB7&MsD*9{!d~FlvJSHx-*L%(%~tcWKy9Mt?H;TeIU1tL1TJ22Iv5={Q8j!A6EBN1Bv3'
    '?Qk!vzZm_^>Murr^$ssGY=Nl182#0-9a{a(vM5?6&Fu7BH(<uYTQf&Sf3W(a(XYR$80?ArJyDo~8&6ghL|iW^1>JUfXSLb!nwHY<'
    'NP9R&sHhCOpE_nm_A4XdpuY_Io8Dejf9lT^?&npt!gJ00jBLUxs-aUuMrorEi>F9!W|Hqh_18|c6gSD(m|`=|ooF0KPJB73-i4w6'
    'rx$nJ&o4i}-u!X1)UG?(3&_r1Kz8;5Y9>a_#8NXc!zJ0ae(5*Q@>SiHO`v^c%*$TjWnefn8=TlT!BnMC!Si5@AX5+IMUF+wL|TCP'
    'yTg>uMQ2OUEMfug2FRA6v8ay&kV!#f$+jc7n8VKgGR5jX2~+m*l1vQ5Cc%sdC}P>e(m{+)?8Hv&#7^wl7?k#_U``pwnUyw<Cn#ch'
    'p`-2H_#kW%y8hWx@9ERcpJ^$5y-HlMnI#NKGdkSKrv~6-BcxqICvh3Kpl{m~Tk|6$<O>34A^?`J;MonzlRA9kzr;&Iajm9N9gDP1'
    '9W8?heH>M-rf4}74_d-?)6xiLrO=JWI}9pJQ8VvBM!KD?v-PWQMf|Q*r5NIx`{~wliv7>aDYhg%y&hw4FY)v1T8Ko%p%kffmfoq_'
    '{zHZdF&O4Z9{mbi5$f!p*P0)hbX;ZkPT+Via0Z1*AWB#6`pu6qt{mc;BBk*M_e6lV0lv1(vk~Oc;&$qp7WadXmLZHQF*IKq4L22S'
    'P!KKds~OMM**aTywCcgu{27p)R<K)DIbB&TN9L)}>PNuKhHb3X5jNT8%zewbZJHfF)o>~ysqW{6v6+>Z^Ag39%Safvc}ZPn9V+IT'
    '6h1qr*TVMv^NYpw(`GS^VTZ-^%=i9u?9BImT19{J7*>|thjF7RHi+SICS-~17NvE65nFGS+AAp^t!m9#RI(^jC1wjtMsEF&pDPwd'
    'uq0Q}U#Xr$wlJZL6jsV=Vn!*Y0`!~0`fg&){?6!N$^l4N<}FM)flBK;#*%|+_fct?hZyiUN`}86!m5L{qgXzOp|uMJs=Nz440&?U'
    '43^F3;A6#nws<e_Fntqq7&Y4)MGtfi3vI$vr8*uiZ6`*yhl}PrfVYi{RojEd#n9Q246l+A=6Q}xd6jrIIQG`r5HIL-osEPY%nRTS'
    '4gYA};w&!PA0pd=lG!THz!stFUo5)jw^io)^w|};lGxJ<7NnAP>n=b%YVbi9N0Yv*#l;mNpzxNJnyY9*gSS$%7f5uLi@^Y%t+REu'
    '&epH1#m;v!d={!KBtP9+j<Nq`(H(wx{$zStuHOIi(~RDbt9Z7Om%U0zCl##H>jg#FHI{g|XHu%v9aZ6d12UoCKFE~k$>7qfFl$*1'
    'ZROmMWVd=pFnpM1t~aav@D!=Z`wV0(OQn#RdOxzBeUUERxL9ga)n6>SB<MPjg`X-xaclM~@r$B^4%xh-kJO%8e^MK4{bi}fb?MS1'
    '9l?jMdFhB2T?tkuZBWttE7B3-<W9Pi?xZ{EPP&usr2DndG36`Mvvbb4=LeaWH0O8|7DgB++oUz!;AB}nlgH3464C#9@uo;OiRk@m'
    'Rw9a>5Ld9|L&|_7>xw}MhYVv&g%<Rr9)!%tSf!?wODsuX-S^0>$Gv1ijx>_yBo$BUkdlT@c8jGDDN&?ZDZ-N+f+H<>5<*t~88U)5'
    'LX9er5<JNuJOfK7c48-XVkh=w4A%|PoR-a96=5Oehb)=g(H?B!mj1UT{pPLQ%okB^#>&DraFZ;SGvkzVBw^<iD_`D~BO~kx5|ld*'
    '*U<7{O_mU||C+2)KS|B8a-5FR4~+L$<>Q7-`YNbL^Y5w%9^lgY{wn*Ef8D(P=J!i^B<|@ic0bMZcl@x`pPt#@?EZH4Kd!&p{ZD<q'
    '#qK904O#u!?vFG5-Fp|?{CirxesEokJt50Lxdfz3>CPL~*m%gkI%JZxoa#`0v=3(-u)pmsVxLzv$YkDR=@hS15ng{FN<{&#o8tr?'
    'q&7M?jdRvYYKlGk3y($lms>IIi}qxxr5$_qN%c+0T6YqAPA3D!iM~m+Z8KA_Vb!hLj+?XsqlnqEv=>!yBAr@8q{HeIVM146m>G+Q'
    '7}|_#TS0BRXAq|71aF83ac8SiC39S;$_p&PSuDZW-!u}D-LwYjDH$O<{TL(-k@g)TbRrW-{f?3Hm5^+%sv}6)kJJN5*@GbEc9p!v'
    'P6Pz+GVu-}w!#-61hw^y|4<rZCcv_-6LCU-=jqQ%RLQM3wqzZZDNbOkWR{bo*sRK>5F<}9=XGL#I%gEYSk2hR6FHGz6Jo~tM)bBx'
    'Iiy-2G2W{^$RcF??-wECQhqbP3mETLvixTMG4PJx4gv6kSBFw`UzMi_==tm~4HmaE%&!1ZQU*_#kU`jXQXF~_Vva(hHY^tYGghwJ'
    'Y#JPaDKeS{MKX~D`0Jp~&`Bhk2&-K>iKGKa+mA$`sXdO+Ly`0yBke>ckn+utbO%x&f)I3ZxEsmV+sGZLeI!6tNl;;$7%7$=k;N?9'
    '{wTKli|za}K!T0*VFMiLU55<cqb{649kT&z?RxE;Jb{a<7_99C+G|Q_RF$2Sa}+h8%ES>pQ^-u6$cg+WkQsp^ObQ&PspJsC{}%D%'
    'U%iVTnXb~u`^Edez0U*s7&X|r?xlKf2+DAwg6jC$Af<w+eGwTq-y7Y4!(p$Y(wZI~G~O}7EGK0{y%F{j@>_v5P+EXikO(ax)Ec;p'
    'gbWhRa-~5>e}mQq!%+wFW{p_{g;k|OA8q#?I(yIFv-j*ZdLvY(C3NIPc&=h~`rW<DdHS#4&(m}ZL4UvKeF#A;1vv7-c*!4u=Pj5z'
    '_kn&+ZdmuxRdQ7hk6cVykKxR}uFLR7pf52wNc9DFs5pJ8w`Vzh)Vm^O7S%#rk64s(DKIytTbiRHEp(#qcJoDAs8wG@%eEkQmje1='
    '1>FkzU`enF`WjN{7SLCbkd1`sY+A0y>_tT~zWKv6{$UivQp`JsWkD0@i)}Ff)no6YZv{lJKT2$Ok;=2SfyhNt*VW2(%BkqRC{^Y1'
    ')fpJ5^K#+iE}>5h-1imfa@-d;U7rz&8AE-Xe`I}GM4HLI+dJJqzMIv&@5_CZTfdn_rv0g+kFTK2zi#s{OF|!1L|s;7EkdUaAsG*f'
    'p0I#x<R4tluK!~>yDsi-F~pbj`6UKoS-_C{dj_Il2C{Mn5@QCEa|SYV1_E{lqICwoe#o+i>X~P7E@vQBBc3AzjsqpO%svm3Kp!w1'
    '(u~U+(u873upRBI;QK0;E1^`0`cNuQ=re)((ENeamzaM{XW!X(_8saglYMov@5V^$6OEdbhoYg*n(Ql+yelvV70{RG81v#tY>+QR'
    '4kXEA6|<Ho>*zGY)eibIdEpZNPvsS#KW|(@<fCDXX_e<KJ|eQn2-ogK5<arBV7HBYtyNkt2_9IcGj-F;9m+2!av~>kB0o0Ljv(1Y'
    'WC}~izvHpUPHz##MpV<PRvPrV>3u>(l4+KtlCu&rmaA`Z|I0qQo`=&#EFcO;QW1iO?3P6`ih^g1YBWIJCc&!2UYnz$<7*K5AgN@S'
    'Dap8SHUHNV`~T(TXL{#q;>8X3{XajMTEub$NtVVnN1*ee2D7Ywd|x$m0|_R#?^NVALdeEoBihq=fJA8twvjeQNGWFX5J{pwvxgLk'
    'MD3W2+^rcB#z<3abDBqr!S>S(66I@~4<MG=s!bt+d9DT$O$jIJ>=y`O3Lk<<QHo2xt!BeQm!Lpg#pDQeJw%$A0)FxtNamBnZZ-1V'
    '(nh*lC8!5Q$aX_El3KuyNe%+?Y>$v^B43m=dqaNNfusfv&Mrcx1D1`%F;Y!0G#jzY?d?IxxX~FzAGz@W6095bkTgIF_GNPsU<L^?'
    '$HBr={NIbF<n8rRS7l);-aaX&qN=aG&E-+5q)e?DsGgF#4j>6pl8ub4ky6c-;p&s0$xsW3k4r%nrR($_D)OkJvV@~09=RrKL>2c@'
    'fqF!n5p+N$ZHQ=+Evh!40%aV!)6cN+3#x?0rMswvfR#CufzvJAN7aB&4zTNM?~Z6v@mvcQ6=ABt<!DY-FjbArO>-|5OH3uGGNvm1'
    'SI<!;Ohq;oOLUcaRkm;+70a=t&#U_J;hw4@E@lT+*JLLc?~a`}GNQ_gs+d$;GeQH-wR?_gZIV?1vZpGXig@=N75P+^Q&rA{if)4{'
    '^6t2~VIQZGUQnsx*no<fimL3OG9neyKB~Nf$|$Z(22~E0KxF!X-bsbI(dv4sK9VXZ1q9?^4^a`ON?P%R?ST8KBBml}@|>f}K2^X}'
    '5gJrSRLPOX=BSEAwFn6R&!TipFF(ht(lILepac}L_ZWn*fWcMI-QW#hM3n=!(~B97O{9(DndvXVMgcOiROMU7k*HS1b{Eyyp!(vL'
    'GB`G4wGm_oZYE%~_lf~<6%ebg$%fG2q4p6^1do*>l|$Y9khM*V0rZHug=TB3YrmMPnPw_rJT=R_GKEaV$RTA)vVI48odxf#L(1em'
    '`kX^U$n!&p2Zj(Qo{;@i?Ui7!9)(on5m9G&k&4P}JfgmshE$>&kBHc2%YUXAk0`OCB3b&&qQOOFm}3KgLy$%x<(8`l7fsVoGz~l?'
    'a)b4Ti(;%F?J<@40AO|(<NZoHomZ8IM^GMJ8N1p>P-uLeExgMl8Dw+&5LrHCC_y#11@A%@p5othhRksB;Eu0BSTg(Ahk677K_)kL'
    '2Us$r<TpwX20rNJTn(v$U?J{qoq?@C38y|AY076EA(nHt$_|mGB~#sy)+QG5Lg^bK6@sD=P~ANb5zUTS2+)d^0fO{eb%+#`g_}Y6'
    'unBq5XJO+M!-k2qe6}w@wy#PXXW*_D7DI@2EFa#B7OO}mt4J_d;p2qL1|K4fbvBX=g_Vbp&_E$1qS%#AhlCKaa=O(WNWzMnesDIT'
    '_@_956qDuJf!O@u1g9A0k!T{pWFZ|SSv;|WkY#&xkT^nuX<`hPA+hd5$VXsZw&)`{Si|0nq-Ob3*$5f8(+AQ4#412{1WCs2_((8+'
    '$3zBc-{I`oh<!Wu6ezvbs=(3Ov7476c$OJI(T8qeal%F75zZ5~yl;!)6Vh>>-}B;d&nqU9%{_0Ie?l}jDU^J`d!-gp;{RQ81AP>a'
    'OfMh*_Y+S++I<In!|*R!8*DMRT_JA7uh$z;Z)F=E@!q11*rbAm3VU0*dzz6H8(M_H5VqdLd%?i8WX`!^*c(O2OK^I*w}l*7@p=n%'
    'Qa}TXa9|M*!RW1?`%^M>MBvrMy94gUHA-;rjv+j2V0X{Wo`KylH&mQnDc=^f*$c-Lw!<m+A=FD;tybhw%#~JXU?S6IaC#&6TB%Td'
    'f_u5%Obwx!y=n+D-x}!MwyKPV;Pk2?u)TVF_u;@A96}2)_#>bY`3jGr`+JMo3;&iA`7bRVg+v#R!WcilM9MEQCYCN-+b2ztVL(H+'
    '%yWb$do<}mG^1JENmGYYI7id&q@g`Dc{qi0H03^;*2WVwK@)e;w7Y1?wn6TqNfYn$qi9+iPtXKS)WJ!JCXH!o8ch)O^~6k?GNehj'
    '+H%eW&C%rHDr4T()z%pdCNc6TyE|yACqZwg{XUvv>L>=2m^e+f)i6Gd%wuZPqybGB(L_m;O&WI+NxBUelP3B!Ww_rZ-@R{|M%lKS'
    'O_O%fWMc~5Ndz>-)S<-((Kr*7v=wcJrrDahw2LO2H0C5mlm{|9d%Q70Gc+)4y6&gJbswKY14)#Cnn&8nh-r%PD9n{;&{SJ%e4Hj>'
    '+hVh|&HHGwshg%<G{u-^V-jO)Lq1W^zzL!$8pDseS<{Rs(R8lUG2HGXn*P%|dfS`Cc!UN_P_z@;S8JNlB$DNuJV}#{M}a0WS^mb2'
    'WrMVL$L%Jnxzlv&mSS#L1(o;JxvP*Lirl8ZCe5Od_{)nz;`Q?-XXK)fc)wi!`%@Tgwry}cv;l!#GT1rBno;o#o^<Kh5cA**3Y4Lf'
    'cZ&sYCW(iZsR1P6$07$HGpqSH^6GOU1A`q!au5ee8+PIGQFu9qhZA?__g;MZ`Gx!NdJrf7{nBCdc3vG95B~dU>@Qs@6MuiObbvYn'
    '3GPqXzyaTy21iI5$QNlK5~P7NaNzr$L*BW6V~Bgs5A5>__xC*5zenqH`2OUB`-98{khJ5si$@T%#C}jYx9-Ff9`A14@&u+yygdnz'
    'vv@x7XW%r8Kk50WNxTl;pAlXL@9zlD{{CR$X|O*ue}9PsJo)=uZ2tbJ8T^C|#bqD@WnVsNlM)mSKHmI~r-1-B63>nZU&2`aS1z(?'
    'xX7ljA7L=@^^>rbvp?4&OfH&yYjSbzwq{DBj8qxDCIINAJ%wx7qmHe<KG)Z-`l?`TjR)zXNOLgyqy6Yrj4s<elyEL*n|(2_f|Ajg'
    '*00W{lLC4t`J98QEZtAp!TV9aZv~@R0VDQR!CMR0!T`~PA9uB#DB>K7ohxJkBIR}Fph;xnRti+dbInI1EF3TNus&+}cO)0(xl#6^'
    '(M1D4boQaC1SgJ}vKwL??nCJZMAM0WU9|l;C{3dIyF`oYX!Ja^?)NpDMAbH0y+`PyR6V1As@_Bkw1EBDnyfg129pac&U7S8l<Ceg'
    '>xN~*0crou_Vd?h<*PB<PdF)Qw;>b`tEt!r7TK<f9AgyhS=7gKBfC$v--m>RtiGq38&6a`ujHVs`MQu{JIjj8Ri2nKu94ZoB4TTI'
    'DP6Pc+>+;I99WUkg7@x<N`6@+*#F|<?!8%8$+WKeQXr%m`^>Z<NgRpkmL8$(bl(|&$#}5+Gsn4Snh3;dmc%J*H<$(c$WvWd=_Mou'
    'A^#5*{h+)*RMdo}Vlh&%XbKuq=z*v?vQ<G=eu`kL&hl{zvec6@d7aMKcZ8x@6k!KNK2Bk2J0D9S*ZY$x+Hs1wgChU%6lQwRlj5X!'
    'I7R->DfYZk;YXpU$0>H~xa9#9`8Y+IrwGR>hNt=tiZOSQA3zaCTu!}%B2Dvjc}NjPoMR0m?z0Rj@{q?3BR;tfx$$CBq>)sBj2oOH'
    'jii$}l5nt^yp8;F!%(0bxiyU=KjKhSONWM;M<Qb$NWfBxUS#mUda)wM&59h~<?!HGk)s=*{C;mf9{u=cCt=X-rhF^*IPST)7Wy$>'
    'AA`pMZh9!xFzJJE%n8BS!>)tA0}mrSxx4HbrvV=C#DjZId<^g|oCbKj6A#`=_%Xoya2nuoh&LAxHcr=Y6!UZ}GdK<KX!0v<3J(^3'
    'OZJ$8kB5V}nHX{sPj}+&xp=%2cLKO(aFA)v*ZH2f(np6UKA*eS$KC5UJsH3E{l0g98R20TkM91vRXw)wRF2{6_ZIK`+3xcoPPTN<'
    'pYuVy`FI@T?)ggtJl%<VS_kG}cMPWip2m3b`70NXcj7d_lc!Iaz?+Z9L-;-)>*mWh+GhdcaUg)D0p6aB4+Yd?0&X1OPTt*sck!J9'
    '{>1_EL$~l>F1m%d=@#BEm;c(j1?QJN_w?jt&Z^E#RA&~e{V^lq-M0Fkfkkh%Tkk@4R(f`p=?*OGodfHnJ*+qy^Wx|lj$pyVl6rmT'
    'FmkYX5L+FvjD7qNMh+GoEI2+PE|wgO4r0=YFDvIj&D#|lyXplTjEc>#QXcWT9-q7m%X7T_4lF$ZYsawYW8nx!$FO90MR^`mcVhJk'
    '*h9w&Wb}v3_2Fk5+vC^ZQ{IQ8?`CwdV|z$Ailu`XIhdylII$D^j<96AK9eolMcbcOa^;@&_Yv44kNsB{f9p*iqd1Bfrh%+CmIkfT'
    '8Au=INNQ#l-BohRh8%bOGvsD+o)FS96z3-_iZ-H1BMm_u>JXCh{Wg|jM~%ayd)*~=sqbe722t~XU-Toq4aQmdcRD{Jjm`ljQa3zF'
    '0@jNKSV}xKl-@>!;(#Mtgz|tg%h{wL<1N<|a+Y<licJC66oG7W)l@Z&DR9(s00|$8siqlI7&|!WkfPlbQF~_SJhqY|?50Rc{i(O4'
    'X$teuibINEM^>y9V!}Li+E<{UABG~G6hAsedmIHRuI&*Nw3|YwR#6mDvX^AX9jOw|*_Z$t`gD&e;tq=PL<*cd_~8_Kkv)TgY=`V='
    'inxQKSX=!L3adoAez$FkW>L_PB3gdmc1*KA*v1sennMuZY*9p|HX6C8!}8*6sDOfuSEvH%#yse;e>u#?SuF}aBQVsS^~GlRpRQjV'
    'kvzt}7*eqCaZC~0F(2}Q)YzIY-J(M)jg8l7AVUYQYP9?s##1j^i@&yLE#A@^CH{U1qr|hmpNe%NPo|=wH-I+Ff+wc^(7_Q~o%wBT'
    '9Jd0w)syO^I;l>olj@{;GS!jzrITtzb*`_I>ZCfUPO6jYq;h;Xq7t`}H-{44kzYqrY7~%9FKSPKudbh1bSnS#Prv&|pTFExD(_d8'
    'M&(!!m>)2&;CakwEY6;@=j=Iq&YrX9H{7F6Pj$lTQ#d{5d|x<-|K^>8$n?%Xe6SGt?VW|lS69*m{T=V`HEO>^Y`-Gx2%Dgx>g+vx'
    '&)&25>^*x`x{62jhI@PKj^47PH}B{T^Sy3>fzeB>iq)1$qIa3t&i$_beD4Xd_4d`pvhp!WOb65VuG$o?JyHc5(nl*IX6^c8(1?R8'
    'z2oBQ(9s4KlxRbb8?*ihdN$Z6h|ua#CFZ(smYoax_}^ZfdgA8P^T~GV0WNW0pUMd3l4YfhV6bREbTzdhcxuh-r}LP~N{uR${gg2k'
    'S#f4YVjqu6*SrH%WGzL>%7-zPT^S_X^I#@V$YZKBNJM7*prORhW2%JWOca$@MI}4K!f843n5ucDJ+t$JFo|;>Qzhhc4_@p#row4-'
    'Bo+KYkaD?>sf@fmf{JjQqoBgW(qZs*Ol74TQm%{>-v!-E14{fnq#}6O1dzsIIIFSEP?71o+EXRNhn7>d8LHUuG0UmQcDn7T+6<K!'
    'Uo~_!zLP3XQI#pG`ar5SN0slS%H-T6q^c9o(ckZ#o5WPkIh3ZToSVc{b^LbtRL)HrRC)Mr52);$G^pxmXBtu2H)&Dj!H(&P0@9{D'
    'M^y*=JsQ3~J9bfJ_q2k;KSE{Qr0p+oFO_wZng>9`KSX8Rq~>7I@DEWLHwpMJFnou~E_-3zB;X6d@I9*RaiTL+@FqQ~>hjSORPZKU'
    'su{zTONDOIrK(}<M6!OF?|cG%bBf`v1Dtx=ewUbsQ!P4`|L&4*^KI3sykCB#+w>Wc=b_PO-^k_1yp%hR*5gD^^h8heL{IcYe>>=#'
    'Zwtw;4dggV&9{ggN1KO6yOd?<a#<ZflZ&<iT4pRPhGpe2nq0Jb<u2kKD7k1FqMoJ3LE{}LHLtiuYNLXm2hnH+Qw%)(23~=-j5iYG'
    '1ZtLo$o7yPfd*@TGeJ}(NqjiC9}ez^Jv6yxD`LG__W%1u3eB5k|NZjAvY(s@ASF~MM|ONB^++#JZR)JMZ0h1Vg$Sg=d$Fjocy0*h'
    '1y9tNIvNjiA2mIgx?t)$rcMv0u7|1HL#V5-XPu#b|H<?S>V!{ElqZoa>iQ6B0uM9w-4oQsppFNrdqr%11a%1qsr#_V@EGcZn1LPC'
    '3$wb9IvUjaVJ1eMht%Z()VzP=iSmP}!$ImT0abVubvj6$H!0;2)LA<{&Qh1{2LpV$cT-2@dzh!F>%*zVLW#nZVN$ml>NH8+0QFTo'
    'ouJMW)N}`R64ioi>H?^%ppJ+-%~4B}v`t+H)Ip9hvXt--q;50R{i7#YnD0(%VqPVCsFMuozmvLun2MSmqmo(+6*JUiQuhy2#|=8v'
    'aSwHyq26wZbT-+CQUBhfu3GLX-;^52Jt)KOA!;BYK9f2+)JbiU5wdd6r`C+yx1x6PB=4jy4t1EI4pY?S7`2L7+D9E8M@_a*&DWq#'
    'I))@aks4_LHis+;+A1OBXaki~o39MtBP!I&X;)_US*5;}&ze!wh??+re2jY0dHxTV!b)M)dA?s>be@D&p4|@^^@mJ~iWd8rg0NR}'
    'l26ufN7Jr*!b(yc4JX_BEj3oe!BGYU)>K*)`2iGVNKp-n-w!FifSWNXGN#CTD2hR$&rV4}J1Ck#0rIK~im->G7!-&R;1sljq8SwW'
    'W+X+}Ls1M0bu)^Bc2G2fBI>h2P=q}c#h{QkqbX<yMKdVm&1j0ShoTr1N$OD!P>|HFC<<{ihbY9&APPRzV-);m5JeQutVbyL%|MF8'
    '6&Hsnh^sRI1sm!?3U)J?q95u}ivDIWML*ObMZpwdOp$uM!hoU~6tsup3#RC9<`+y6_E0o~A`L0%0Tgja5gtL2h7|Mwia4YQkDy3H'
    '3VHxV98!cwP^2LRJ%A!UfFg`3(gP@HND&`E5ylkh0TeW(h(NRAQh@TTp*bQu5Vc`inK1<oDdH}QMF#&LFEaS24;ehaESK>$sN%*('
    'u!&kUc|_3sn#6YCis$nKoshuq2!%);eT9*k<ua#aeaZG5lkp`zzX^kU`UmZ$3M%&8#|BgoU^O-CbySKdG!U$u%3!)I4WG=511jPs'
    'LuDIG{Tuf01S%Y*d#v_Gnf6nV5o1?0h2VONUbAD0Vm$_{hG90(7Kfr4bG(Zp8&6W?0&^(}oZ<r%D0>(`(jP(5Jc@?T_uUjQ9Yx$h'
    'ksm`r-vdQ?3<WN4ds6%cD6&<Ucpn9Q4;0}s6mbVdHiVah6cO*Ih@w1-B6*(E`2iGs58p*WLfeaccV{VzC1P3>Aitv24{C}qOF=mJ'
    '2l*!`ol+T6D5aZiCQcTGEiXrHx5DuV#dy{MWs8(IlT4;2n_?)zD2if><q=30{7DgzP6$MH6ex%lArBcpgVTr+bM*saR6l7}jxmB!'
    'QKsC9g;N@R#f0!`r}Wt&L{A9f*RjY!F1mofzUTs8ulD#4JpjxuD((SBY84k91g@ckFyObz{jd?AR{eqHeZz)1wIHjE;|tXj<!$-H'
    '9F?rAAzk5!SihNElp1({HChoG??40as+mR;p4q3P<Z>J*`fxOVqo@Dq6?@N{;=iG34)r&R{d<nTU%7jozfZb*tg}Dw*!k}`?6QaY'
    '#cJI{HhXBX8JL+&(kFVNCwihk8cLp!6<r}Mc|sn!hC|<I_%w8p+5X1Ge*1Z~-@d)R#801;{WdvLWw338)+ChCw|GP&X<CVHb@WTt'
    'YDjHp@Qs`Em-$7c)T35TZN`||Ut^2u38?Fe{Zn(rM%>CYwq;fsRwJ6mXsG4DaEfW44Z6%tvKg7|&?p5S*&0pTP77$FsgZPPnxzcX'
    'Q7+Z-^obKR;1M=MuL$elIJ258-HJ!!XsneYCEGOdUYcsEl&5H<Ofy51_Rv_?%}JV}UFfUPlrXjreU~%?t5>yY(n)jD7<&0#G-Z}1'
    '{#Z15mL}|?DLZK_y_7?f?xm?{8DJXnXv%|VaxksH(KNgS+eUdOO*I*ZIT|ut_~vMeZ7~BJS~B%<C79lSz?hya=SHmuL|l`}2m_kv'
    'a1PnBRD&BM(^Xl;uR@>rYTB#ya)I&=RC^o7;$qsQ<$w|t2-yrpLmuoOYck}@ZeyT<SUDq}`eN?*YhVF}!GOlnyQu|8ZQfArIhMyZ'
    '@kMRoi_-YMjJRcIs%L&IPyAS&xO?-9+Qg{S#HeZJi)PkGniw^Wy&=TP&l3YGGrFXiA1f0-Hl?^K6R%mD7?ANr6I+AYWM))pZDIp~'
    'gQ5wVFhfHVG+~Bj!o5d+Q5ipwGJazR?l;X3r}?1k^}K)cqUVjPZw}E*j0yYZ*covr4TO#&$y{?*uITD5p$S8#$*S)D606o#a-Et)'
    'K)XeOM4UDhOe}SeS!Ifb6o7U2eT<G#q<IRnG8KJYifU2Blj0~vc_sx7*VscT!f+)IDeCZ@E5|9~aEFPbT?$!4j6J9fcRDk!iyS2c'
    '-%rg-jJ`tF<a!PrhIPQ7*wtBQ4Z>5uVpbU4cd(lkJn@%cU)3;tF6NW-)n<95q?)9FLp3P!@KhgDl;ad>$X)E9XvZmN2Sq+i5g$rX'
    '4pW336!n=DX`Z4Tr=T4a`H2*<jZXEiLjfMlGbobnA9{cyk2sVGiZZ0ABYsS$16FRex;#+TM^c9R8Lk~ex)7dX5D9T{NWoQ*kRpzi'
    'YjLc7eE+4gN$G!Uk<tTQr1aN!3H|*tzG`o*k1scsj8sOy1(XH0PND!!&WG+A2W91eU3}V-5z62m<YApA#dk+LFrl7WbBq$){3<X8'
    'M74RdFJp0UY-H@k%BVr=Wny*~_9C*oW*Y&!Ikpj*2zM^(S2t%UMhJmNVj#rdGyZ_<070Cag``=8*}|$}NsGKT6=yFk_cejAtX`Hu'
    'm6~Nnl}P{avb8Nqq?(BFPU}r9ni^lba#x&IAv)T)83k@LKa|W5CG$hJ>Y7Xmi%iKXnwrIE3v578vz4OR9Ku)oq2awAn$%z;WIysY'
    '*#F_On^#n4(^`<t11--Pp&X-uV{J?(5^WPiGLdMTEs}}!YSjdNf-lEzv8?b^;n$U|^eaL#W=E_<cv*8dJyK1ip<&y|$6zu>0``qC'
    'k=mbk2myX(H@EVPk%W-U4)A^sZirT{tRI(11xU|F5O~8j&O!RxY{I1Uj0qOf`$?gnVayl%8OD5ZPAV$TDV92-s!7{cWx$C8Cy%q4'
    'W77$NaBQ`X)-pM=Oj4V`BF+5mOFn?KN;B`5%YT0g(GiC}hg(@wLmUZPacF2}4*K1d3|uq?vUCg6uyZV^<tpYO*hO(~6aG!{d_SHZ'
    'fLF^G)WJiCmjMnVmD2=X`i)B9G{EDER}XI%9#*^@!_y7V1Kc>lX@GyoU^=PeEFP|S@$l&2*XogZfSVi&P2ttV;{XqrEZ^lgo?5@X'
    'L7Y6CTF)Y3ygGOs;Gy-JCx}mRh$nvHCw}55e&Q#7;?KbcUgBwo_pfK(8w7C}ztEn9FS7UFx%m6OZME^<UY7h0Kc$h5A%7i;Ffi~H'
    'F}>=sh@ePNgkrEllI>`EQk)bg#Yu5eoD?U;N%0$}(As3}uP!;}uS3z0b>~qO(c~@b-4qG<G?bkb$a_`#-2v~GF@>nJmwg|B)KKw9'
    'VH`#x72?)|;lPw&3M^qgt*#wYj9Z6vCx@a7Ua<W=zzpMP!|F(JfC8G+iYcg0xND7Uzs4JwhOsSi^dp`Rk9jva48EieWcP^x;Bk_`'
    '90nvqH(<x?O<)X*9RGK(al1di-30m1A4&DiSu~BWkDySAQ0mYj*UJmBey6)`tC(k9?ateu`u%uJLAF;__4c^X`9sGY6zUz+l?{x;'
    'IM{(-0}5pSRE}o@3eq_N6-D)rg`Of>J0Eh7fm3Qu8K%hiAT=paUEwhWcO6D`g$tZ?W6C1TmBjsqv9G*A5%y4IIHh<(j#CskrFhEP'
    'uq1FBl?0Ba@3KJ=_E2OvrD#HCD2hQ*;FO{%vni^S2FxjICPgzSP=0;$D9&(7^@Pk&RFfwtaMJftRQOo*lqH9v!AaLs=2B!h>1slN'
    '34>Eax4u!Cq^J&yRN<8FqiAr_<&-6#A{!KmQ{({!Wa-$14C*~u6#az635x1-rj|!!M?n)5#kZm5F-5`@-Gro39wLjPn~*j^F|Zf5'
    '35t4@BJH6lj=*py#aMQkkZ$%+Skg~=Bt>;)tT~Etg8Dls!dM<0Q>1B%a0dm=QaIVD;sYqcXi8@&(nttL6pIl4_ZA^Me}4Iyu0r^i'
    '=nLTyhb>h<T5K<U8`2j{zXsYwU;Y<!TTM}3Ch*+CS8*~!mGF~5XtvIXQGjHaoR~qMe(?Rp5!LiQ(meV&MPGgTJf?4e9*K#BVx+Sz'
    'H0mTs2k4#CARVPIKpg?rn@bNC5DG7>_tTdtdcA-m3Q65dUyjm8FSa!wq;He-MT?Zti%bRd;gR$eD09@^HAL@-_IJ>?WAuc|nSjI='
    'Tddtzq>oC%uJVB;Sm=7APlxG|$gaUj`kU-t<fd)pzXJ4aO#co>mtN@s?x6>Y0-!~3>48q6d1?kgpXTW=Yb)t4v>*U|_2^fS=IK+P'
    'a0DwnG`+9>(3+3vDnl43%M1h6NK*9SPWo)>RIbl5aTUpZ^yJZ3t%B(nP?Vmg1A5Z*5%?HLdakT#wyuX1pRAQTJ$;&>51PJzVC2*1'
    '9rP{eoMeTZYy=1B72A~@`Y)<1({dUVQ<Z}0vqN9iGx6wuujzrzN|0r+=~03gPu2AZdN*f&LoDQB`Z_~Tldk&VAbs@IZF}jlE$eI1'
    '=YfLWGlZfe^%y-JruTG^`7nKaBt5Fk=BX#2O^<T!ri1illAauTRJ`)p^wCqP0&FjRI7sj5Zo@tF>EZM!ZBKRd#?Pil*~}_e?*9F2'
    'q}0#x=3(^(D|ZEBROO-gY?_Fb!BI%|P(vG)E2Oc3!gMs^B_Eop8W#VB5MCe+|76BI2J}M`cLu$P4Bo)X!o&t0ZKunEhm2iSlU2nE'
    '>-WqX^Adk$pr<l!j1-N28cDtM`o^4USZ%ADS4Ny#bR8MiG}1$BX9D|zys_px8dUJm(bK@`g!qk-&jnn?;yN_r4g*!IF=T#YG%AjM'
    'vG=!;Z91oMU~QhLWAw{}cWs+1zBIH!+jhp(h8FYP#kq!7;>q%5Lrbw|+1y!AtxV9=du}ZJ;5XLpy0NtH#>zc6_NZkxLqii!Y~~f4'
    'c~vK9X10a*ArGHM>dgZNO=BwiVhksbo(6p=|6H2H)#XO5wK`m8Ya%n7Cdy=RxYF8inWfuF>I`~IQfbn}EnTHK=%~tBz}%$6_vd!5'
    'c{kQ4WitjHkqyomj(1}Tgstg1r**iSL7Q(ihHMX-aCY5{X3)Dati6#kc^PffWTfXc#TMhnlHvHyJxj`HE0302I=_?QHl6IW+E~)U'
    'Hx`>|o$0fZ=F#~>w$+1Y_p|nU;pu~pjb6|#)>huzlk9}eKm`U0<|Zw8J&k5jHvEH&vLU?u{CZP1yc)^|RXgnKP?*`RdojfbtlQew'
    '@w`Q8MrUtPTV@?^m;vuSG~9W{6w%z7z(!ejQ4r2dZ|q5Us0l~L8he)IUk7V-R%1^~J1Cm5=MnVNGO7jSp(>{sS`lzFrmCkJyP=L*'
    'CR>G*XDJ*NPcbNx*0~g)B6`XlgCdT#Eqf>|ZHyRda+1j3v^5TerHA1+6a83XOHad`3kb8g-B6Psk6aBc4)fU<MJ(qys^xA`FhhFt'
    '1-VM5pt2dW$C1<H^3&y@vL(%kc=P(BdXysU(HxESMq`Sxpng)E6eq<=aZ;QVvlM&c5=W7ow&HQ1n2pb*ScLF@xCr4ff7B&;z2rrW'
    'uU{@z7QGNOuk1+hijIWfl^nUEgYY;THH&rRZ;6^2WWsT@PNGO*$m)X_{Fd|@@K9~p#_6ZlHWI-%RS42w7J#By3VX=WD3FOzpr=DR'
    'f$FMU5lX<}Ab6-VWG-3(wAeSqz0TD}m%JOgR%$ec9K2{3j)G#nFyq)d%<SAyaI?WgKUa)9<awziP44w!FB;vW$VY$Z8!EeRC_Vp%'
    'p7#vyxuNizzoGLjx$}lTyEoL_AvbSP#pc}*HSdN}^KK|LcgS8`eAIQ;gNO1VSLcROSIH3#*+X^B^$ZNa@GYUH!j)W9n1qXcL$@(n'
    'LzYai@Knv_4Ut9zKn-h969t>4#X6gd>V{gm=RSUjtRXk^hSCjf&136bG#*5&Cy0Dg)E4EO6eY<;<0!pJaRpEhl|_2xhx3Qz94?ac'
    '>qk|Q#ZCTQdVY-;$(bz&SH0loh|2qv-oBfU`9a6@K+c0qxA;c=rExRuH0<F}V2niS3{UEO5$j(&!^24>8CIa=kJ`;Rd^$Lv3&UhS'
    'i6XDNcE451ycld7)y@Voz5!z*7YS>KJS)?fI7iu!d)R!d0xV)I@5ERr7CjcLs&N1-0Baa)UmMFhiI<1bH^j)o%88xW4(vNy*Hf5G'
    '$lbrwUjci_KDYyW#$L|Ojy8{>Q|&RQ;qLQRtdOjj1Rslgc@2T}BBbPPisYRp`K2OxC;1zMdABN9JT{o^QU_jcU!i%-+;gIuS&SA>'
    'TVM<>aqnCdESaOtdr$D}4zEA(AG1E__-c9HQMLrgKDEeIv6rhpf5=sfSMVMg&yx-vsgnkgI9_sDujr;1^H=sthvZ-rDnHMat~df`'
    '*|jJ<_2b+cEIZaNIoRy0QXI>Cag5BxF|`--rG?2BevdF>ayGznFfr@-MWNqfSRFq16FadJJFycxu@gJ7J29uO0?l$^RwSyFOiVw!'
    '$772u^V-WY`D!D2<Fd>!)FOMvf6pJmP5R>0&~cO3*p-F`Omy`gUvN0(Y<?w9S!M(mnm?GJ)28ukv-xvIaJCwZho!b_>CRx$@=7(V'
    'wwcQoFqNh@y)#VuDD-JFvnA*CMYRMLQ6kL^%a+U;ow|Im-rkB8Q^q9}X1y9lK;65-9aZ*X&|xxbOqLmd8O6p}gxGDK@*ylFfX(Jn'
    'oKauQV0oXN-7N=`9DP?B+x0!ojhBeZQ51P$hh^u{;;QWSW*JnbeG_xkXVp0!i-To*n03D<FFC=8{T;++D-NmZVXhk|I3U;W&;=2<'
    'h<uG%g%ta*Oj>hg#f?*A*)gP6tFOLMEDxTfW6}F-kxG>9%_4zFLBqQK1e^tay2!u>c1KZrpy3CC&g$T>4Z&d>94@6!F|}S9>G&{C'
    'q)cJW#-f9fgL##<9R}to<C7fB5d*xU;^bh-!R)Xg{Bza$x$68}b$;$BX4+p;J7%|WefnIFzU0*!&o{dhAz3YOS&i%?ARY4Oi;kP5'
    '<5%tl;ipMozdUaYNsb?&BgaKYjw1(iEG0+fzdf>HbvF6B;{eEp<FXQ-z|oiB;gBJF-JeqtVN$R{uT%n9HZd(&b(pNiRS_2TK~;8O'
    'eFR}PF;Z9`iWhcZ-Q#-|n8%&&XOwBgxi)9}@dB00m~%y#r<%$(6YZsy&BqM$ZIE6!e3jkx*bW*GYP-_BJ-Ir&tHiREag3U+kBy^g'
    '^COZxEX^p6>pm<V#DW)*^$aZiim>_}Vda6?On{$<g)v4>O;wcEt^h$gD*dOHzB1UP35YAkA)bI3Rna*klwC;?N{I_AyAo4QBEhi0'
    'GrafwlM1cAov=*YWo}f_`xPBX-Sj3HZq}};=H+tmws>+3C~it;H(8h`qeX8uV-?sUJH1W$?4{9H?<fa@SM@_xzdK)cZ|caw(m`zM'
    'AkK~nFz?}sT&zv;QhARx(!<i671JyH<{6p+W<G~LA$nFrDHawl<swWr(!<O(k^0oTSq;U)E(SCMBOf!@C(pT_)ldv9@|3z+{oDa8'
    'UF(KoTXM0mC@QvRtrXskB_7cr^wY({R2uiJ<$jD+6H5-J?6)ABH^$68i<I^;tDztahMY;euU9Z#V<edn#xoRz#Scvm!nBE8$Z{TL'
    '$4om(p_&^!9uHz(_;&gsu<{*Y`Kx1(;3rP(#2$n>44SiWZEgBKdul$8Ewap~PL_EMS3A%vh(E&Sem*isd)j7|c^=m0vGM>cIy=u%'
    'jGX8GAgn%Os?+1AGqib6$D>mnCb6T_c@*=fx*oCux5HRIf<-44sgKn|pCiXsGj_~!ecARp62r0=JLU5|nP`He?TYP~;l(pg$N5$5'
    'zD3?fR~}$z_I#I<<C4+#V4kN@a}HD&%lBfg1GYwsV{|Ldf+~&{sXAJ#y6cs3lQGhaxoWRNtsAxNdAQQp<+R$SW)~}aJ!>XR>HE#>'
    '@h)tN<I}z=Rk?BiEa{vC1zXP*Rt?*I1l+V?<d4cM#Pc|Fa}qbH6l3B^HiUV{I^Pno*}$3LnIm8V=`Lx8wUQGo!M3K*$ohRO`YXA~'
    '&obv%nO!@$5$E%EpmJ=l+G*9i#f{AWEi%{VUgnBdnTsr$i?YKadEA<p6T<UY@w~;Iy<oq~O&YnhJKyMSbl=U#>h9h6U@(GXPK?f1'
    'rej}8cYUQ7p-~PROZT46^!T`y8QZKUk~lwCcVh8i^w1N`#NO`dMRn3ajJwJtC?Qm^_w*PUUiTHudWVtaB44%3SC`~WCG?F@=`NgM'
    'i%t-;VWgP$4b$i6iv6Oo<f!0NvpwMtVAa8zlFvo@CO$F`<A!~Xk%L7C<KBKduyik0HAdeN7N3o!uZWd9FuE5j+UX`f7-Oq-9;*N&'
    'xeJ4>s0=ZJSRP^#V(2^)f<MAw#DKsEY(5#W1@heLZdWlt-Pq#LH4j*bATPH4psBEfZhLWFyW}XB^21~@k7;tf^`ShLdU@=P=dFld'
    '?Jl=+S3ar{&yGgCc-nFg^J5LLD)T6o9*Nb1SQ%q&FP5Kxg&`LAV)Y4F8Dr$!`a`jBAC~M}-zr*wmsRUV$icXKRdKLvSniMsCtE5U'
    'j;Z899R?g54J<KC%5`1M^y*+re`nQN@3%K)7bH6cK(DSu*yg^k^Yvsykro+dJ35FA2W%H65LRlNdF>;i`B-uMG0MRMAv@YZC!Wp4'
    'oM9fpMqzhHFh`3S4`QBvIE}EdTca9AMj21HdjK28TJFb=+M_(JY8ok_kLF`}Ml|exvtS!4ls(Px!K^r*`uC`6_-JCE-I=4G5Sufh'
    'if&=2ZkP@ltta%xWvAYFMyLG9tW!w%TV%C7k+)*(8|2oS@}hcLn7284wo1n%W6kuGjPSWmkD1|Jt6Wi03N{s=P|~24lsY@ZNftk-'
    '%<<A9&SM%YJ`g>OqzPQv&L^;lyms;!qk~ww3(LE)2A+zG;k}rEnCf8}@eN4KG7@z#o&rhbDm@W+()`tm&}P#WMJyU?YSD3Vk-tW4'
    '8;IDpbou)|c*7<=+8hr$*JID~%JZ_ufQlgagI<V+=U$hb4|-X*yi8uM4_$M<)JsN62c7-gA0!8h`=-rP=gmE*w96~8-@kt`u!{(7'
    'q%Hmsg_EUxssSg{C9W%1I=~`lph|skg2vB`-hF=hk%LK9HG5n<?@=^%4S+FoG8vAk`b6bim6XrO!J>l&X-_Sf=QpqlF?s?Phgi8A'
    't5_oSu!ONNg*7aU(-4!1XbZ-YG@VKB=!`i>efDErL()!=!gN+3mlvDEt!X8Hg+eG9Zq%^us^?+t`N0S0G!`G67a#g>bwU!#oE~VA'
    'oxUL1iTfSWNR!|v5h{)u&rf%6-g+CP!UrEK!RCCRP@SZ+0n{)g!wj2|(^wK5CNTRV>A!bci-@5XSV7u=2F=<9Fxzn&OVIpYz*3xP'
    'Wnlboj)C8BIT>N`0G72&#@*OGE+Aji#pM}To5jkv#|SWv55w9%EL#3&(^%2`CqGaOj4x&Bm#2;;&!3MDV$s3)*&wROvB8kxAjy0r'
    'ixP5F^|^ikWcn9mmG`KByecPB_dN<Duv`J>qcKuXr2@m{Gjh$f3G4~J!}TDxSB*V`?bXuXSs)?rG&J1l51;p%d&Xv)Cj=Ml4uLpY'
    '#^IoeZ)k1YAHa7oiYAThm*L^RmUr8w)4-gacN_9uR||5((H)0ACmp--x5#6E<Xs-4w|8+Yyj=eC)6)58-#g!y*3T4P-Y@8yj3aT4'
    'e9>l@s94XU-WtFFXK_t{F_qT|Fn*7`o*9ER{-8Z|tC|yK45`R9=H{ohJeQZ{xqP}jm-zC2@i{*Exdh|6<ca4}?wIo`k5It0Rdt|f'
    'hi_nuw62r%BFy?a%4_5#B(AG*-J5%QZBv$<lD>xJUx=G6yS=8b!_r&ZGTL(PB8MczEF-;HrrV0%%nj;KE*sRRTb|SRtB*9N+X9`v'
    'N@B(NSB1SO_Elytm%I{3l66(ZRWh!MxFU9yC$1t>t=LzrIGlIYyOE+R?cIp4g1S2Y&cE;eZ`q;#^S}M~E5EepwBMHSjeHH=;6if+'
    'D(-|GW1<d^%u-_OudUM(oT%-<wKn$&-KQ3ubXWyowyo<Vt_$FANT@6N>j173_vL|=((Dr$p1NsF!Ut2q4-x-lXZ7w+&bwIs^Y8ro'
    'E$`7kzwgkW(y~Lp<(K!1x6A&V%;2wINBjIc|NQsjcMIo|m-iySE-yuXTltm@1X{(nRCUxxoy?#}Ep*cSNpr4yGwCy~XU1TTpR}PX'
    'WA>-76<L5%ApVA5+jG5ryY;s01Am_F179wFIcg&iL3ExQJ#d>67RiE)Q@jOyt8pu0Q}okX^CNTbk5E{1Ml&d8m$Zj3ewEHYYhLt9'
    '&W~Bi#aYSKTf1KC==$V7PTV7idmQu99{dI~T%buWP#lwi+$O8hN~%?i7O7TtTFkyyElXUIPRzW;mk+b`aTkYTtvV8^gn0zR<3DB+'
    'iX_{K2XF9LFqeV+<BLD%+tr^ly)2h8ep&rFy>ub)7_na61~LPnY@Xb%Y9wmUHVq*sl4#XN2-alB&54IS5arFQBDa(BT~~oVK?mIx'
    'WvA9dE;65a)QNAi+zd$<ZqD+Vf!oS50#Dyo3pyxDrFE4w=t*#U${Y<D-tK%aR37+M)8ruySYR?ZAcCCcGDTnn5mu6hCTP%mQ^mQL'
    'Kv7&t)5bIr72Xvzq;i%Vqe&<ul%RoydlXF=(ZmTF0$D&bO&QXp2^vtC4$z=&m#vLBL8ER9&?F=Au}>2@O-6Mf)O!j<W<aBTZRDOn'
    '6Evs{29xNjdT&C1J7EplG)hEndnVKbC>pEGa#{Cs+APcFS&%yOQIK32-MnqL_<|}o@zmXxN<e!ZbbnjQyEAS9tG6LH!{hWes&Y%d'
    'qT{;z1@^%)CKwBMTVS2rEaD}W-m7~@L?Ma!`rc6IZ%{OEL$}$iie}}J=r-gU%=`iAmN%~k(=%<otzy!|^?pjQ9OJgzD!~fMS#N8j'
    'DR9U`n%tdHINQrssxn(Nkw;7$G_`+mVg795G!aKll?j?Wr0L!p?m;4NYeZ9rG&DhzI=?oH#`b!V?59f;Cupd5^D=45kS0ygFj3m1'
    '2_u>~K|@RxfY%18gafFEne=4SG+fe$G*Kr$h&m!v6&+Xa7fsM49(M`%gv6r|APq?JKssT7;><OTRz)O7v}4|6hBTTwnhI~rIxjeP'
    'K<harg?x45M<r>><Oo$2vmzjpCG%;q16BxXxQZHhZ^QvBg)k)a<M)PtQS~(pQx?&VWYKH<u}hq4yy!KEUY5)FiRbu9?c@K^--&%M'
    'SQ_OCbHj!FXky5s8y|Ecu*po7a$CF6PSS)mU+Gc`9jCWymvZMYEmr*410Y5p<$&S5r4K%Poo^AopRX8!6eBk*g487Iv-L1tMWL>k'
    'I5k?2MP)?Uu%KA|4ofo2K!=euD|A?tsWmz*$V4bTmTJ&K7g+P{9xU(1Zcog{s)IET%MMl?ta(^_3RWEKW2^?&+F>j^m|JnNI+$Av'
    ')hlz0igCeh(8~*Sw5%fSN<=hQ%Fr!y=w(H6QZ%`Vrj8EOEh?Fufzqy2THa%F){|FmxlJ!baxn3&**S4@us^s93mz67%q-u1AC?@9'
    '94vTPaxikRcn}L%dvYI^23V)bEG8Cjy6p{<&fgGQbFyeGu4=ap%bcBn7_DNZ=0k3xVmB{UDj`jb^F&2z?K_P7NNjw8VtYEifOJN&'
    '+O0E{jILXsx^U#iE2{0IuJ1#&&T#8I0&694tj=yp(aFN(?kv&E!bHvS>?POhcjKo{+3*L#E`de=?mza~vc6oiWkpb>GmR1txK)nz'
    'f{XS-4bB1|O0xJDX~=BCLVZzWQByo)AM_--CKW){jih%bl_}lWmczfYLY)*7Y()W0(hh)CZn63YWTJ^AJS3DSRuwy}a#sjCjfTds'
    'UzVH+QXY*}$oou~Lkc(oysQ`|lK`@bsnz$$ikdUkHuqxBEPwgH(wL9NVE(2b3=>>~tvB3>wG;bcv0vS~&d%E1iO~#J9*4zeVqQkl'
    'z1Y2}(H>dLcxp56l~wkklT;ncUcp{1qYNp&fXAF<gUxL=7MtQ<wBfoRjN%&uuJ>6WXCSN|AXi`!kFWwJj|JT;hiILbN3DylhOd5x'
    'Fg4pcQt$%Myz;nCiwJBVsyhsC{^IAVr$w^*!~cNN5WjK3Dh-m8`9))#bjiMe--07=dF5R^WrJ%Kn3lynC9b2tk9+j@bxwor99Ld7'
    '1P>$D8PSW`d&d-OT_#xPqsX03E0P<i9n!e2k=;Tk)@5y$T6+|hmFEU<>`1z#W|+aq#Z<La?TC}~)Aq37V(l1~o`4Z5oPNWcd(g{l'
    'p9=7PEZax_PR#SGaIrLlc`B~z@Gq{dwV?pO?;bN4CUBR#wIyCUS+7{!(HeSQ5?4@?Fl8H)dp$d&Ft_kQY-6b@9}Bg^04xG$d$mj6'
    'FsKL%suXIov8XWN*CX6#x?i^fB4e||BgxY21yzZ-IXA1!;2F;!jV$JKmUa*G>K*N4MW!&X*ppWzs@Yg{FmkZuU||0#&gN9?pHm_i'
    '!kUf2y>OzocXF_1W6{BmR;6z?79WavsfTS(S`Q=71J}cn6Zd<`a<&L-f9_pY`}}sx0Q&jungNs#4n-C??dp!7%v$NVjRPd`K`=2q'
    'x_fwe&+zV_t-5Qr()Tu74}O?md$!J{e=hxV>HmPU)xPCyEhp=rTC+aI*Gu}hC4EPCvi4cIKSMc+W%Q<I$VC+{k;wcmGQ1HZTSa6J'
    '2NlkVk-gl`WZodJ!&zu632Z@fP#b4+chb|M#PJch5lVrJgl9<B29Y4O2;iE;bp_YSxNgpM(KeWwYnr{z^VjJ&a6LUIgSp-Nyn?)*'
    'N%C9=>y0MXt*pNQ-v#MbTL$l!S;!#?DH>fz;Z}wA2eyY0-?|Fa;s}4Nfc7*p_PxLZrV89kdEEvhvk(ty&2VpzNLw$@2x7{y49}X-'
    'ABb<46YNjp6YLcqT+#fIG9KanTW$F8P0%PVC!ZaB<ELmXhh!`VQ91;kaZ?LdSi-7t&E5<vX}k3r);;gJcU^!IGC3Pk1K09keDqFx'
    'XxFX3((7-`A&{{K<n^d(L2?epo%~td!TwoA5gbml7}pbw>`YmrJZ86daqSlK&jkTPp4caf7!plj+kb{<4HKSTxeWG4m(29>=7{os'
    '6<=>@29(jJU^7%gnsBcB=B8&}YPsqbH;wWZw+nyUmN!me-gWL)wB}1mlap9A!WMc)!i66Aqls35Eds3!TM@JjL!})PfO553nOmvN'
    'W^RqUTEVa}dg)n3`c%JFO!bi8;`xB)TU=oier112h9DQbvLaZ!1-=jPtwQe~!S@!m65I=(*P0)hcYgu-b5}TnQTl)x(L3x7SWc?H'
    '_<mC5Pq&lm{i;8ynvu{^I@dtwAROK}j?IUzdzM)n8?>?Ax$4nIZ5S?$*Ab@;&-Gn6(<9I5K5KUof<L>}$QDtR`(2Wr#=t+Kb$QOJ'
    '7VqS1SrqFQ8ca94eVs^@U6C;vCobIAi&7R&_u_<xX}%Z6vl~^Cp$k*;G8(|V)rKGI1AD{KUVR5Ud+Vr|M*hRNH;=ZN2puCL^hS)n'
    'zk7vST|vDSZi{H$HMAO0npqq(h$9f6(;M&Z4SRaezgcF>INl)(FtNQAxK3-BSkuu>VU)p-$)DTPi^HY9-`@N0c+dR0yH1^Y@_3aP'
    '*^9~Y->$+g{U?^_99oqk%cV+t5Ul_l_jpB*!2FgtbeVIqB<NGN_@nTHmr57~lv|Ie=N6+Mkhq43ncnhS^(t!^Tc&U$6}n5YeRnc$'
    'Mk=DL)D?RuD!!HbDAL!Y$TmfL97UO;FrM5rMcqM>tv7N^k<FDnPf^S_N>UV)qFS417gbK9sK=Z}QA0V6VzkRJK-k=0sEu|p8hr)Z'
    'D(i4F9d5{ZNHIJYgu+>7zv6F%rI4rwMPvhset-ZQNH%X5BtVfdr+Rux%sP2Ft&~*^4@6Ul07~Z8fgeA)(Wi()C(tA}YB>W69bF(O'
    'Kt@dhsfW0%N#L>Z$4ekAn@5kTsGZgtf4m7u(fsiy9Yb6B<4s!GR{2T<Iom1^bWJ*{ruL7oa*CDT?B@(b*i`;XV2Z#fs(fsfzY;?V'
    'q<gG#A*m3eYU@|}2sylG_Hq8cCPb`gph2-UBneu|P}WuPS`<T9mAr9eQ~kmWYS9b5D&{~EH0Ie9XsAi=a8}$^wuUOQoq&OeFxKSh'
    'tgV3%*lH~bYgXll-1x1EhblJgG#Q}E2Vzr{Aw`9%dqhF@mlzbksG+JPwWFa{kg!799`ySyIVtjE&#Gu+b*-LPG9Rz9XXtgNBK(Uf'
    '>yARs9D$SZC>A%jXbb+#Prv&|UoOgm^!D<8kysv&WXj!V|JnZ?_FJ3SkKTVi-?RS*?*G33E=jHa)8Y*Oc{vC_rI+`M_kVx7p3}Vu'
    'gB+aIF<zyXlj+m@Q(mM+lJbwdCLtC-`g&#z*7(^yk_x1+YOdHEM$X6A(*}895&wmSnG2US{N?5S;?qYh@mcBMN9#ZTejR`3`aJ)B'
    '1N-wI{K5YZ!RQn_'
)


@functools.cache
def font_data():
    return json.loads(zlib.decompress(base64.b85decode(FONT_DATA)))


@functools.cache
def glyph(font, character):
    advance, left, top, width, height, bitmap = font_data()[font][character]
    rows = bytes.fromhex(bitmap)
    return advance, left, top, width, height, rows


def text_width(text, font, tracking=0):
    return (sum(glyph(font, character)[0] for character in text) +
            max(0, len(text) - 1) * round(tracking * SCALE)) / SCALE


def wrap(text, font, width):
    lines = []
    line = ""
    for word in text.split():
        joined = f"{line} {word}" if line else word
        if line and text_width(joined, font) > width:
            lines.append(line)
            line = word
        else:
            line = joined
    return [*lines, line]


class Canvas:
    def __init__(self):
        self.side = SIZE * SCALE
        self.pixels = bytearray(self.side * self.side)

    def span(self, x0, x1, y, color):
        if 0 <= y < self.side:
            x0, x1 = max(0, x0), min(self.side, x1)
            if x1 > x0:
                start = y * self.side + x0
                self.pixels[start:start + x1 - x0] = bytes((color,)) * (x1 - x0)

    def rect(self, x, y, width, height, color):
        x0, x1 = round(x * SCALE), round((x + width) * SCALE)
        for row in range(round(y * SCALE), round((y + height) * SCALE)):
            self.span(x0, x1, row, color)

    def polygon(self, points, color):
        points = [(x * SCALE, y * SCALE) for x, y in points]
        edges = tuple(zip(points[-1:] + points[:-1], points))
        for row in range(max(0, math.floor(min(y for x, y in points))),
                         min(self.side, math.ceil(max(y for x, y in points)))):
            scan = row + 0.5
            intersections = sorted(
                x0 + (scan - y0) * (x1 - x0) / (y1 - y0)
                for (x0, y0), (x1, y1) in edges if min(y0, y1) <= scan < max(y0, y1)
            )
            for x0, x1 in zip(intersections[::2], intersections[1::2]):
                self.span(math.ceil(x0 - .5), math.ceil(x1 - .5), row, color)

    def circle(self, x, y, radius, color):
        x, y, radius = x * SCALE, y * SCALE, radius * SCALE
        for row in range(math.floor(y - radius), math.ceil(y + radius)):
            vertical = row + .5 - y
            if abs(vertical) < radius:
                half = math.sqrt(radius * radius - vertical * vertical)
                self.span(math.ceil(x - half - .5), math.ceil(x + half - .5), row, color)

    def line(self, x0, y0, x1, y1, color, width=1):
        length = math.hypot(x1 - x0, y1 - y0)
        if length == 0:
            return
        dx = (y1 - y0) * width / (2 * length)
        dy = (x0 - x1) * width / (2 * length)
        self.polygon(((x0 + dx, y0 + dy), (x1 + dx, y1 + dy),
                      (x1 - dx, y1 - dy), (x0 - dx, y0 - dy)), color)

    def text(self, x, baseline, text, font, color=INK, *, align="left", tracking=0, overprint=False):
        width = text_width(text, font, tracking)
        if align == "center":
            x -= width / 2
        elif align == "right":
            x -= width
        pen, baseline = round(x * SCALE), round(baseline * SCALE)
        ink = bytes((color,))
        for character in text:
            advance, left, top, width, height, bitmap = glyph(font, character)
            stride = (width + 7) // 8
            x0, y0 = pen + left, baseline + top
            for row in range(height):
                offset = (y0 + row) * self.side + x0
                for col in range(width):
                    if bitmap[row * stride + col // 8] & (128 >> (col % 8)):
                        index = offset + col
                        if overprint:
                            self.pixels[index:index + 2] = ink * 2
                        else:
                            self.pixels[index] = color
            pen += advance + round(tracking * SCALE)

    def block(self, x, baseline, lines, font, leading, color=INK, *, overprint=False):
        for line in lines:
            self.text(x, baseline, line, font, color, overprint=overprint)
            baseline += leading

    def png(self):
        # The packed channels each have ample room for the sum of nine samples.
        # This integer box filter creates no platform-dependent color profiles.
        weights = tuple((r << 24) | (g << 12) | b for r, g, b in PALETTE)
        rgb = tuple(bytes(color) for color in PALETTE)
        scanlines = bytearray()
        side = self.side
        for y in range(SIZE):
            start = y * SCALE * side
            rows = (self.pixels[start:start + side],
                    self.pixels[start + side:start + 2 * side],
                    self.pixels[start + 2 * side:start + 3 * side])
            scanlines.append(0)  # PNG filter type 0
            for i in range(0, side, SCALE):
                a, b, c = (row[i:i + SCALE] for row in rows)
                fill = a[0]
                if a == b == c and a[1] == a[2] == fill:
                    scanlines.extend(rgb[fill])
                else:
                    mix = sum(weights[index] for row in (a, b, c) for index in row)
                    scanlines.extend((((mix >> 24) + 4) // 9,
                                      (((mix >> 12) & 4095) + 4) // 9,
                                      ((mix & 4095) + 4) // 9))

        def chunk(kind, data):
            return (struct.pack(">I", len(data)) + kind + data +
                    struct.pack(">I", zlib.crc32(kind + data)))

        header = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 2, 0, 0, 0)
        return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) +
                chunk(b"IDAT", zlib.compress(scanlines, 9)) + chunk(b"IEND", b""))


def masthead(page):
    page.rect(24, 16, 976, 2, INK)
    page.text(512, 35, "THE WORLD IN ONE DAY", "bold13", BLUE, align="center", tracking=2)
    page.text(512, 79, "20 NOVEMBER 2026", "display55", align="center", overprint=True)
    page.rect(24, 88, 976, 21, BLUE)
    page.text(512, 103, "FRIDAY · ALL THE DAY'S NEWS ON ONE PAGE · 40 STORIES, 6 CONTINENTS",
              "bold12", PAPER, align="center", tracking=1)


def summit(page):
    # Three seats at one table. Flag motifs use the paper's red and blue inks.
    x, y = 484, 148
    page.rect(x - 40, y - 14, 104, 56, WASH)
    page.line(x - 22, y + 6, x + 46, y + 6, RULE, 2)
    for dx, country, color in ((-22, "US", BLUE), (12, "CHINA", RED), (46, "RUSSIA", BLUE)):
        cx = x + dx
        page.circle(cx, y + 6, 12, color)
        if country == "CHINA":
            star = ((0, -6), (1.5, -2), (6, -2), (2.5, .8), (3.8, 5),
                    (0, 2.6), (-3.8, 5), (-2.5, .8), (-6, -2), (-1.5, -2))
            page.polygon(tuple((cx + u, y + 6 + v) for u, v in star), PAPER)
        else:
            page.rect(cx - 8, y + 1, 16, 3, PAPER)
            page.rect(cx - 8, y + 4, 16, 3, PALE_BLUE)
            page.rect(cx - 8, y + 7, 16, 3, RED)
            if country == "US":
                page.rect(cx - 8, y + 1, 7, 5, BLUE)
                page.circle(cx - 5, y + 3, 1, PAPER)
        page.text(cx, y + 33, country, "bold10", color, align="center")


def lead_articles(page):
    page.rect(568, 119, 1, 114, RULE)
    for (place, heading, body), x, head_font, head_width, body_width in zip(
        LEADS, (24, 584), ("display27", "display22"), (415, 416), (528, 416)
    ):
        page.text(x, 129, place + "  /  REPORTED", "bold12", RED, tracking=.65)
        lines = heading.splitlines()
        assert max(text_width(line, head_font) for line in lines) <= head_width, lines
        page.block(x, 154, lines, head_font, 26, overprint=True)
        lines = wrap(body, "body14", body_width)
        assert len(lines) <= 3, lines
        page.block(x, 199, lines, "body14", 15)
    summit(page)
    page.rect(24, 237, 976, 1, INK)


def card_illustration(page, x, y, number):
    page.rect(x, y, 48, 40, WASH)
    if number == 0:
        page.polygon(((x + 10, y + 33), (x + 14, y + 9), (x + 24, y + 5),
                      (x + 29, y + 34)), BLUE)
        for level in (14, 19, 24, 29):
            page.rect(x + 15, y + level, 8, 1, PALE_BLUE)
        page.line(x + 42, y + 8, x + 27, y + 17, RED, 2)
        page.polygon(((x + 28, y + 12), (x + 24, y + 19), (x + 32, y + 17)), RED)
        page.rect(x + 6, y + 34, 36, 1, MUTED)
    elif number == 1:
        page.line(x + 5, y + 23, x + 43, y + 23, BLUE, 2)
        for tower in (15, 32):
            page.rect(x + tower, y + 8, 2, 22, BLUE)
            page.line(x + tower + 1, y + 8, x + tower - 8, y + 23, BLUE)
            page.line(x + tower + 1, y + 8, x + tower + 9, y + 23, BLUE)
        page.line(x + 20, y + 21, x + 27, y + 25, RED, 3)
        for level in (31, 35):
            page.rect(x + 5, y + level, 38, 1, PALE_BLUE)
    else:
        for height, left in ((7, 9), (11, 17), (15, 25), (22, 33)):
            page.rect(x + left, y + 34 - height, 5, height, PALE_BLUE)
        page.rect(x + 6, y + 34, 36, 1, BLUE)
        page.line(x + 8, y + 25, x + 22, y + 15, BLUE, 2)
        page.line(x + 22, y + 15, x + 28, y + 19, BLUE, 2)
        page.line(x + 28, y + 19, x + 40, y + 7, RED, 2)
        page.polygon(((x + 34, y + 7), (x + 41, y + 6), (x + 40, y + 13)), RED)


def secondary_articles(page):
    for number, ((place, heading, body), x) in enumerate(zip(CARDS, (24, 268, 512))):
        page.rect(x + 232, 246, 1, 99, RULE)
        page.text(x, 254, place + "  /  REPORTED", "bold10", RED, tracking=.3)
        lines = heading.splitlines()
        assert max(text_width(line, "bold16") for line in lines) < 183, lines
        page.block(x, 273, lines, "bold16", 16, overprint=True)
        lines = wrap(body, "body12", 220)
        assert len(lines) <= 3, lines
        page.block(x, 310, lines, "body12", 13)
        card_illustration(page, x + 183, 260, number)

    x, y = 756, 244
    page.rect(x, y, 244, 103, WASH)
    page.rect(x, y, 244, 3, BLUE)
    page.text(x + 12, y + 19, "MARKETS", "bold17", BLUE, tracking=1)
    for index, (name, value) in enumerate(MARKETS):
        baseline = y + 35 + index * 14
        page.text(x + 12, baseline, name, "bold12")
        if index == 0:
            page.text(x + 59, baseline, "(5th straight fall)", "body12", MUTED)
        color = RED if value.startswith("-") else BLUE
        page.text(x + 232, baseline, value, "bold12", color, align="right")


def project(lon, lat, box, bounds):
    x, y, width, height = box
    west, south, east, north = bounds
    return x + (lon - west) * width / (east - west), y + (north - lat) * height / (north - south)


def clip_polygon(points, bounds):
    west, south, east, north = bounds
    for axis, border, direction in ((0, west, 1), (0, east, -1), (1, south, 1), (1, north, -1)):
        result = []
        for start, end in zip(points[-1:] + points[:-1], points):
            start_inside = direction * (start[axis] - border) >= 0
            end_inside = direction * (end[axis] - border) >= 0
            if start_inside != end_inside:
                fraction = (border - start[axis]) / (end[axis] - start[axis])
                result.append(tuple(a + fraction * (b - a) for a, b in zip(start, end)))
            if end_inside:
                result.append(end)
        points = result
    return points


def coastlines(page, box, bounds):
    for line in COASTS:
        clipped = clip_polygon(line, bounds)
        if len(clipped) >= 3:
            page.polygon([project(lon, lat, box, bounds) for lon, lat in clipped], LAND)


def map_numbers(page, offsets, box, bounds):
    labels = []
    for number in sorted(offsets):
        dx, dy = offsets[number]
        _, _, tag, coords = BRIEFS[number - 1]
        x, y = project(*coords, box, bounds)
        color = BLUE if tag == "REPORTED" else RED
        page.line(x, y, x + dx, y + dy, color, .65)
        page.circle(x, y, 1.6, color)
        labels.append((x + dx, y + dy, number, color))
    for x, y, number, color in labels:
        map_badge(page, x, y, number, color)


def map_badge(page, x, y, number, color=BLUE):
    page.rect(x - 7.5, y - 5.5, 15, 11, color)
    page.text(x, y + 3.35, str(number), "bold10", PAPER, align="center")


def world_map(page):
    page.rect(24, 353, 976, 1, INK)
    page.text(24, 370, "WORLD BRIEFS", "bold17", BLUE, tracking=.7)
    page.text(198, 370, "Numbers on the map match the briefs below.", "body12", MUTED)
    page.rect(24, 377, 976, 124, WASH)
    page.rect(636, 377, 1, 124, RULE)
    page.rect(824, 377, 1, 124, RULE)

    box = (31, 381, 590, 113)
    bounds = (-180, -57, 180, 83)
    for longitude in range(-150, 180, 30):
        x, _ = project(longitude, 0, box, bounds)
        page.rect(x, 381, .55, 113, LAND)
    for latitude in (-30, 0, 30, 60):
        _, y = project(0, latitude, box, bounds)
        page.rect(31, y, 590, .55, LAND)
    coastlines(page, box, bounds)
    for number in sorted((*EUROPE, *US_EAST)):
        x, y = project(*BRIEFS[number - 1][3], box, bounds)
        page.circle(x, y, 1.5, BLUE)
    map_numbers(page, WORLD, box, bounds)

    page.text(645, 392, "EUROPE", "bold10", MUTED, tracking=.7)
    box, bounds = (651, 399, 160, 94), (-13, 31, 43, 62)
    coastlines(page, box, bounds)
    map_numbers(page, EUROPE, box, bounds)

    page.text(834, 392, "US EAST COAST", "bold10", MUTED, tracking=.7)
    box, bounds = (843, 399, 147, 49), (-82, 34, -70, 44)
    coastlines(page, box, bounds)
    map_numbers(page, US_EAST, box, bounds)

    page.rect(825, 457, 175, 1, RULE)
    page.text(834, 470, "SPACE", "bold10", MUTED, tracking=.7)
    for number, x, label in ((12, 841, "Voyager 1"), (13, 926, "Mercury")):
        map_badge(page, x, 486, number)
        page.text(x + 12, 490, label, "body12", BLUE)


def news_briefs(page):
    top, bottom = 507, 976
    page.rect(344, top, 1, bottom - top, RULE)
    page.rect(676, top, 1, bottom - top, RULE)
    for start, end, x in ((0, 13, 24), (13, 26, 356), (26, 40, 688)):
        rows = [(place, wrap(body, "body12", 287), tag) for place, body, tag, _ in BRIEFS[start:end]]
        heights = [14 + 11 * len(lines) for _, lines, _ in rows]
        extra = bottom - top - sum(heights)
        assert extra >= 0, heights
        y = top
        for index, ((place, lines, tag), height) in enumerate(zip(rows, heights)):
            number = start + index + 1
            color = BLUE if tag == "REPORTED" else RED
            if index:
                page.rect(x, y, 312, .65, RULE)
            page.text(x, y + 12, f"{number:02d}", "bold13", color)
            page.text(x + 24, y + 12, place, "bold12", tracking=.18)
            page.text(x + 312, y + 12, tag, "bold10", color, align="right", tracking=.3)
            page.block(x + 24, y + 23, lines, "body12", 11)
            y += height + (index + 1) * extra // len(rows) - index * extra // len(rows)

    page.rect(24, 980, 976, 1.5, INK)
    page.block(24, 995, FOOTNOTE, "body12", 13, MUTED)


def main():
    page = Canvas()
    masthead(page)
    lead_articles(page)
    secondary_articles(page)
    world_map(page)
    news_briefs(page)
    output = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
    output.mkdir(parents=True, exist_ok=True)
    (output / "entry.png").write_bytes(page.png())


if __name__ == "__main__":
    main()
