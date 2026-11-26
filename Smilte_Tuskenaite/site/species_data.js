const SPECIES = [
  {
    "species_id": "ambystoma-tigrinum",
    "common_name": "Tiger salamander",
    "latin_name": "Ambystoma tigrinum",
    "flicker_fusion_hz": 30.0,
    "body_mass_g": 10.78,
    "light_level": "L"
  },
  {
    "species_id": "anguilla-anguilla",
    "common_name": "European eel",
    "latin_name": "Anguilla anguilla",
    "flicker_fusion_hz": 14.0,
    "body_mass_g": 71.1,
    "light_level": "L"
  },
  {
    "species_id": "anolis-cristatellus",
    "common_name": "Puerto Rican crested anole",
    "latin_name": "Anolis cristatellus",
    "flicker_fusion_hz": 70.0,
    "body_mass_g": 6.0,
    "light_level": "H"
  },
  {
    "species_id": "asio-flammeus",
    "common_name": "Short-eared owl",
    "latin_name": "Asio flammeus",
    "flicker_fusion_hz": 70.0,
    "body_mass_g": 406.0,
    "light_level": "H"
  },
  {
    "species_id": "bubo-virginianus",
    "common_name": "Great horned owl",
    "latin_name": "Bubo virginianus",
    "flicker_fusion_hz": 45.0,
    "body_mass_g": 1450.0,
    "light_level": "L"
  },
  {
    "species_id": "canis-lupus-familiaris",
    "common_name": "Domestic dog",
    "latin_name": "Canis lupus familiaris",
    "flicker_fusion_hz": 80.0,
    "body_mass_g": 13900.0,
    "light_level": "H"
  },
  {
    "species_id": "carassius-auratus",
    "common_name": "Goldfish",
    "latin_name": "Carassius auratus",
    "flicker_fusion_hz": 67.2,
    "body_mass_g": 10.8,
    "light_level": "H"
  },
  {
    "species_id": "carcharhinus-acronotus",
    "common_name": "Blacknose shark",
    "latin_name": "Carcharhinus acronotus",
    "flicker_fusion_hz": 18.0,
    "body_mass_g": 14491.0,
    "light_level": "L"
  },
  {
    "species_id": "caretta-caretta",
    "common_name": "Loggerhead sea turtle",
    "latin_name": "Caretta caretta",
    "flicker_fusion_hz": 40.0,
    "body_mass_g": 135000.0,
    "light_level": "H"
  },
  {
    "species_id": "cavia-porcellus",
    "common_name": "Guinea pig",
    "latin_name": "Cavia porcellus",
    "flicker_fusion_hz": 50.0,
    "body_mass_g": 629.0,
    "light_level": "L"
  },
  {
    "species_id": "chelonia-mydas",
    "common_name": "Green sea turtle",
    "latin_name": "Chelonia mydas",
    "flicker_fusion_hz": 40.0,
    "body_mass_g": 128000.0,
    "light_level": "H"
  },
  {
    "species_id": "columba-livia",
    "common_name": "Rock pigeon",
    "latin_name": "Columba livia",
    "flicker_fusion_hz": 100.0,
    "body_mass_g": 315.0,
    "light_level": "H"
  },
  {
    "species_id": "dermochelys-coriacea",
    "common_name": "Leatherback sea turtle",
    "latin_name": "Dermochelys coriacea",
    "flicker_fusion_hz": 15.0,
    "body_mass_g": 354000.0,
    "light_level": "H"
  },
  {
    "species_id": "felis-catus",
    "common_name": "Domestic cat",
    "latin_name": "Felis catus",
    "flicker_fusion_hz": 55.0,
    "body_mass_g": 3054.4,
    "light_level": "L"
  },
  {
    "species_id": "gallus-gallus-domesticus",
    "common_name": "Domestic chicken",
    "latin_name": "Gallus gallus domesticus",
    "flicker_fusion_hz": 87.0,
    "body_mass_g": 2710.0,
    "light_level": "H"
  },
  {
    "species_id": "gekko-gecko",
    "common_name": "Tokay gecko",
    "latin_name": "Gekko gecko",
    "flicker_fusion_hz": 20.0,
    "body_mass_g": 54.8,
    "light_level": "L"
  },
  {
    "species_id": "homo-sapiens",
    "common_name": "Human",
    "latin_name": "Homo sapiens",
    "flicker_fusion_hz": 60.0,
    "body_mass_g": 67100.0,
    "light_level": "H"
  },
  {
    "species_id": "iguana-iguana",
    "common_name": "Green iguana",
    "latin_name": "Iguana iguana",
    "flicker_fusion_hz": 80.0,
    "body_mass_g": 750.0,
    "light_level": "H"
  },
  {
    "species_id": "macaca-mulatta",
    "common_name": "Rhesus macaque",
    "latin_name": "Macaca mulatta",
    "flicker_fusion_hz": 95.0,
    "body_mass_g": 7710.0,
    "light_level": "H"
  },
  {
    "species_id": "melopsittacus-undulatus",
    "common_name": "Budgerigar",
    "latin_name": "Melopsittacus undulatus",
    "flicker_fusion_hz": 74.7,
    "body_mass_g": 33.6,
    "light_level": "H"
  },
  {
    "species_id": "negaprion-brevirostris",
    "common_name": "Lemon shark",
    "latin_name": "Negaprion brevirostris",
    "flicker_fusion_hz": 37.0,
    "body_mass_g": 92987.0,
    "light_level": "L"
  },
  {
    "species_id": "oncorhynchus-mykiss",
    "common_name": "Rainbow trout",
    "latin_name": "Oncorhynchus mykiss",
    "flicker_fusion_hz": 27.0,
    "body_mass_g": 4000.0,
    "light_level": "L"
  },
  {
    "species_id": "oryzias-latipes",
    "common_name": "Japanese rice fish (medaka)",
    "latin_name": "Oryzias latipes",
    "flicker_fusion_hz": 37.2,
    "body_mass_g": 0.21,
    "light_level": "L"
  },
  {
    "species_id": "pagophilus-groenlandicus",
    "common_name": "Harp seal",
    "latin_name": "Pagophilus groenlandicus",
    "flicker_fusion_hz": 32.7,
    "body_mass_g": 119600.0,
    "light_level": "L"
  },
  {
    "species_id": "raja-erinacea",
    "common_name": "Little skate",
    "latin_name": "Raja erinacea",
    "flicker_fusion_hz": 30.0,
    "body_mass_g": 500.0,
    "light_level": "L"
  },
  {
    "species_id": "rattus-norvegicus",
    "common_name": "Brown rat",
    "latin_name": "Rattus norvegicus",
    "flicker_fusion_hz": 39.0,
    "body_mass_g": 237.0,
    "light_level": "L"
  },
  {
    "species_id": "spermophilus-lateralis",
    "common_name": "Golden-mantled ground squirrel",
    "latin_name": "Spermophilus lateralis",
    "flicker_fusion_hz": 120.0,
    "body_mass_g": 215.5,
    "light_level": "H"
  },
  {
    "species_id": "sphenodon-punctatus",
    "common_name": "Tuatara",
    "latin_name": "Sphenodon punctatus",
    "flicker_fusion_hz": 45.6,
    "body_mass_g": 353.75,
    "light_level": "L"
  },
  {
    "species_id": "sphyrna-lewini",
    "common_name": "Scalloped hammerhead shark",
    "latin_name": "Sphyrna lewini",
    "flicker_fusion_hz": 27.3,
    "body_mass_g": 1893.0,
    "light_level": "L"
  },
  {
    "species_id": "sturnus-vulgaris",
    "common_name": "Common starling",
    "latin_name": "Sturnus vulgaris",
    "flicker_fusion_hz": 100.0,
    "body_mass_g": 75.0,
    "light_level": "H"
  },
  {
    "species_id": "tamias-amoenus",
    "common_name": "Yellow-pine chipmunk",
    "latin_name": "Tamias amoenus",
    "flicker_fusion_hz": 100.0,
    "body_mass_g": 51.91,
    "light_level": "H"
  },
  {
    "species_id": "tamiasciurus-hudsonicus",
    "common_name": "American red squirrel",
    "latin_name": "Tamiasciurus hudsonicus",
    "flicker_fusion_hz": 60.0,
    "body_mass_g": 215.0,
    "light_level": "H"
  },
  {
    "species_id": "thunnus-albacares",
    "common_name": "Yellowfin tuna",
    "latin_name": "Thunnus albacares",
    "flicker_fusion_hz": 80.0,
    "body_mass_g": 45349.0,
    "light_level": "H"
  },
  {
    "species_id": "tupaia-glis",
    "common_name": "Common treeshrew",
    "latin_name": "Tupaia glis",
    "flicker_fusion_hz": 90.0,
    "body_mass_g": 142.0,
    "light_level": "H"
  }
];
