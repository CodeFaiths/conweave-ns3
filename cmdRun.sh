#进入docker容器
sudo docker exec -it -u 1002:1002 2daf5a914a19 /bin/bash

python2.7 ./waf --run "scratch/network-load-balance mix/CPEMTest/02_Incast_Congestion/config/config.txt"

#plot_fct画论文图 指定固定路径负载作为输入
python3  analysis/plot_fct.py --input-dir mix/output/medu_loop_20260227_122010_AliStorage2019_9MB/load50

#对比多组实验结果，生成对比图
python3 ns-3.19/analysis/medu_cmp_chart.py  --exp-a ns-3.19/mix/output/medu_loop_20260203_221642_AliStorage2019_9MB --exp-b ns-3.19/mix/output/medu_loop_20260212_093305_AliStorage2019_4MB --exp-c ns-3.19/mix/output/medu_loop_20260215_161838_AliStorage2019_2MB  --label-a 9MB --label-b 4MB --label-c 2MB
python3 ns-3.19/analysis/medu_cmp_chart.py  --exp-a ns-3.19/mix/output/medu_loop_20260223_170032_search_9MB_100KB --exp-b ns-3.19/mix/output/medu_loop_20260227_071030_search_9MB --label-a CC0 --label-b CC1