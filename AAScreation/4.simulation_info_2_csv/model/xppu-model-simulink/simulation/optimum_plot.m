for i=1:10
    M2_min(i)=min(t_2(round(linspace(1,10000,100*i))));
end
figure(1);
plot(100:100:1000,M_min,100:100:1000,M2_min);
xlabel('Total Sampling Budget');
ylabel('Optimum value'); 
legend('MOTOS','Equal allocation')
for i=1:4

text(100*i,M2_min(i),num2str(M2_min(i)));
end
for i=1:3

text(100*i,M_min(i),num2str(M_min(i)));
end
text(100*10,M2_min(10),num2str(M2_min(10)));