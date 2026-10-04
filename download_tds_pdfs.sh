#!/bin/bash
# Downloads the 10 public supplier TDS PDFs for Project A (REQ-2 stratified sample).
# Run this from inside your repo folder (sdlc-extraction-agent).

mkdir -p data/tds_pdfs
cd data/tds_pdfs

curl -sSL -o "01_epon828_epoxy.pdf" "https://www.westlakeepoxy.com/sites/default/files/downloads/gfqy40X24W.pdf"
curl -sSL -o "02_cooltherm_ep3500_epoxy.pdf" "https://www.parker.com/content/dam/Parker-com/Literature/Assembly---Protection-Solutions-Division/Technical-Datasheets-(TDS)/Datasheet---CoolThermEP-3500(EnglishA4)_DS4318E.pdf"
curl -sSL -o "03_westsystem_105_epoxy.pdf" "https://www.westsystem.com/app/uploads/2022/09/105_205-207-Combined.pdf"
curl -sSL -o "04_resinlibrary_polyester.pdf" "https://www.resinlibrary.com/wp-content/uploads/2020/08/Technical-Data-Sheet-Unsaturated-polyester-resin.pdf"
curl -sSL -o "05_grpuk_p502_polyester.pdf" "https://grpukltd.com/wp-content/uploads/2017/08/P-502-TDS-.pdf"
curl -sSL -o "06_chemdo_pvc_pb1156.pdf" "https://www.chemdo.com/uploads/PVC-Paste-Resin-TDS-PB1156.pdf"
curl -sSL -o "07_chemdo_pvc_pb1302.pdf" "https://www.chemdo.com/uploads/PVC-Paste-Resin-TDS-PB1302.pdf"
curl -sSL -o "08_farnell_px700k1_epoxy.pdf" "https://www.farnell.com/datasheets/1558213.pdf"
curl -sSL -o "09_ecfibreglass_ec157_epoxy.pdf" "https://www.ecfibreglasssupplies.co.uk/user/TechnicalDataSheet/3207.pdf"
curl -sSL -o "10_farnell_er2188_epoxy.pdf" "https://www.farnell.com/datasheets/1344031.pdf"

echo ""
echo "Done. Verifying file sizes (anything near 0 bytes means that download failed):"
ls -la
